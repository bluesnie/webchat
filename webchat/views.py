import datetime
import json
import time

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, reverse

# Create your views here.
from django_redis import get_redis_connection
from dwebsocket.decorators import require_websocket, accept_websocket

from . import models


def index(request):
    session = request.session.get("user", None)
    if session:
        return render(request, 'index.html', {'user': request.user})
    else:
        return redirect('login')


def mylogin(request):
    if request.session.get("user"):
        return redirect(reverse("index"))

    if request.method == "GET":
        return render(request, 'login.html', {})

    elif request.method == "POST":
        res = {}

        username = request.POST.get('username', None)
        password = request.POST.get('password', None)

        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            request.session['user'] = {'user': user.username, 'pk': user.id}
            res["code"] = 0
            return JsonResponse(res)
        else:
            res["code"] = 1
            res["msg"] = '用户名或密码错误！'
            return JsonResponse(res)


def logout_view(request):
    logout(request)
    return redirect('login')


@accept_websocket
def msg(request):
    # type1 = request.GET.get('type', None)
    # user_id = request.GET.get('user_id', None)
    # print(type1, user_id)
    print(request.is_websocket())
    # if request.is_websocket():  # 判断是不是websocket连接
    #     request.websocket.send("hello")
    user = request.session.get("user")
    websocket = request.websocket                       # 获取websocket连接
    # if type1 == 'user':
    #     ids = [request.user.id, int(user_id)]
    #     ids.sort()
    #     key_subscribe = 'webchat:user:{0}:{1}'.format(ids[0], ids[1])
    # else:
    #     key_subscribe = 'webchat:all'                       # 订阅的频道
    key_subscribe = 'webchat:all'                       # 订阅的频道
    key_user = 'webchat:users'                          # 用户信息key(值为hash(获取： hget webchat:users 2)："{\"pk\": 2, \"user\": \"lisi\", \"online\": true, \"online_time\": 1574325937.8181572, \"offline_time\": 1574325183.860518}")

    if user is None:                                    # 验证是否登录
        websocket.send(json.dumps({"code": 400}))
    else:
        redis_cli = None
        redis_pubsub = None

        try:
            redis_cli = get_redis_connection()          # redis连接

            # 订阅redis消息
            redis_pubsub = redis_cli.pubsub()
            redis_pubsub.subscribe(key_subscribe)

            while True:
                # 获取websocket和redis订阅消息
                ws_message = websocket.read()
                sub_message = redis_pubsub.get_message()

                # 处理websocket消息
                if ws_message:
                    message = json.loads(ws_message)
                    # 填充发布消息的用户和时间
                    message['user'] = user
                    message['date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # 发布消息到redis通道
                    redis_cli.publish(key_subscribe, json.dumps(message))

                    # 若为上线和离线消息，记录用户信息到redis的dict中(使用hash)
                    # 此操作处理上线和离线
                    if message.get("type", None) in ['online', 'offline']:
                        #  redis获取当前用户信息
                        redis_info = redis_cli.hget(key_user, user['pk'])
                        # 存在取出不存在赋值为：{}
                        redis_info = json.loads(redis_info) if redis_info else {}
                        # 更新为当前用户
                        redis_info.update({'pk': user['pk'], 'user': user['user']})
                        if message['type'] == 'online':
                            redis_info.update({'online': True, 'online_time': time.time()})
                        else:
                            redis_info.update({'online': False, 'offline_time': time.time()})
                        redis_cli.hset(key_user, user['pk'], json.dumps(redis_info))
                        # 获取在哈希表中指定 key 的所有字段和值
                        users = redis_cli.hgetall(key_user)
                        users = [json.loads(user) for user in users.values()]
                        # 发布所有用户信息和状态到redis通道
                        redis_cli.publish(key_subscribe, json.dumps({'type': 'user', 'msg': users}))

                    # 私聊或群聊
                    if message.get("chat_type", None) == 'user':  # 私聊
                        print("创建私聊频道")
                        ids = [message['user1'], message['user2']]
                        ids.sort()
                        key_subscribe = 'webchat:user:{0}:{1}'.format(ids[0], ids[1])
                        redis_pubsub = redis_cli.pubsub()
                        redis_pubsub.subscribe(key_subscribe)
                    elif message.get("chat_type", None) == 'group':  # 群聊
                        print("创建群聊频道")
                        group_id = message.get("group", None)
                        if group_id:
                            key_subscribe = 'webchat:group:{0}'.format(group_id)
                            redis_pubsub = redis_cli.pubsub()
                            redis_pubsub.subscribe(key_subscribe)

                # 处理redis订阅消息
                if sub_message and sub_message['type'] == 'message':
                    # 获取订阅消息并且填充状态码信息
                    message = json.loads(sub_message['data'])
                    message['code'] = 200
                    # 发送信息到websocket
                    websocket.send(json.dumps(message))
        except BaseException as e:
            print(e)
        # finally:
        #     if redis_pubsub:
        #       redis_cli


def group(request):
    """群聊"""

    if request.method == "GET":
        groups = models.Group.objects.filter(groupmembers__member=request.user).all()
        groups = [{'id': i.id, 'name': i.name} for i in groups]

        return JsonResponse(data={"groups": groups, 'code': 0, 'errMsg': ''})

    elif request.method == "POST":
        data = json.loads(request.POST.get("user_ids"))
        if data:
            # 创建群
            group_name = '-'.join(data)
            group = models.Group.objects.get_or_create(name=group_name)
            if group[1] == True:
                for i in data:
                    models.GroupMembers.objects.create(member_id=i, group=group[0])
            else:
                group[0].name = group_name
                group[0].save()
                for i in data:
                    models.GroupMembers.objects.get_or_create(member_id=i, group=group[0])
                return JsonResponse(data={'code': 0, 'errMsg': '群已存在，添加新成员'})
        return JsonResponse(data={'code': 0, 'errMsg': ''})


