
import datetime
import requests

basename = "https://discordapp.com/api/v9"
cdn_basename = "https://cdn.discordapp.com"

logging = False

def login(email, password):
    if logging: print(datetime.datetime.now().strftime("[%H:%M:%S]") + " login request")
    data = requests.post(basename + "/auth/login",
                         json={"login": email, "password": password},
                         headers={"Content-Type": "application/json"}).json()
    if logging: print("           " + str(data))
    
    if "captcha_key" in data:
        return None, ["captcha", data["captcha_service"], data["captcha_sitekey"]]

    if "mfa" in data:
        return None, ["mfa", data["ticket"]]

    return None, ["bad"]

def mfa_auth(ticket, code):
    if logging: print(datetime.datetime.now().strftime("[%H:%M:%S]") + " MFA request")
    data = requests.post(basename + "/auth/mfa/totp",
                         json={"ticket": ticket, "code": code},
                         headers={"Content-Type": "application/json"}).json()
    if logging: print("           " + str(data))

    if "token" in data:
        return ["ok", data["token"]]
    else:
        return ["bad"]

def get_servers(token):
    if logging: print(datetime.datetime.now().strftime("[%H:%M:%S]") + " get servers request")
    data = requests.get(basename + "/users/@me/guilds",
                        headers={"Authorization": token}).json()
    if logging: print("           " + str(data))
    return data

def get_server_icon(server_id, icon_id):
    data = requests.get(cdn_basename + f"/icons/{server_id}/{icon_id}.png").content
    return data

def get_channels(token, server_id):
    if logging: print(datetime.datetime.now().strftime("[%H:%M:%S]") + " get channels request")
    data = requests.get(basename + f"/guilds/{server_id}/channels",
                        headers={"Authorization": token}).json()
    if logging: print("           " + str(data))
    return data

def get_user_info(token, user):
    if logging: print(datetime.datetime.now().strftime("[%H:%M:%S]") + " get user info request")
    data = requests.get(basename + "/users/" + user,
                        headers={"Authorization": token}).json()
    if logging: print("           " + str(data))
    return data

def get_profile(token, user):
    if logging: print(datetime.datetime.now().strftime("[%H:%M:%S]") + " get user profile request")
    data = requests.get(basename + f"/users/{user}/profile",
                        headers={"Authorization": token}).json()
    if logging: print("           " + str(data))
    return data

def get_dms(token):
    if logging: print(datetime.datetime.now().strftime("[%H:%M:%S]") + " get dms request")
    data = requests.get(basename + f"/users/@me/channels",
                        headers={"Authorization": token}).json()
    if logging: print("           " + str(data))
    return data

def get_messages(token, channel_id, limit=50):
    if logging: print(datetime.datetime.now().strftime("[%H:%M:%S]") + " get messages request")
    data = requests.get(basename + f"/channels/{channel_id}/messages?limit={limit}",
                        headers={"Authorization": token}).json()
    if logging: print("           " + str(data))
    return data

def send_message(token, channel_id, content, reply=None):
    if logging: print(datetime.datetime.now().strftime("[%H:%M:%S]") + f" get messages request (reply = {reply})")
    if reply is None:
        json_data = {"content": content}
    else:
        json_data = {"content": content, "message_reference": {"channel_id": reply[0], "guild_id": reply[1], "message_id": reply[2]}}
    open("debug.txt", "a").write(str(json_data))
    data = requests.post(basename + f"/channels/{channel_id}/messages",
                         json=json_data,
                         headers={"Content-Type": "application/json", "Authorization": token}).json()
    if logging: print("           " + str(data))
    return data

def typing(token, channel_id):
    if logging: print(datetime.datetime.now().strftime("[%H:%M:%S]") + " typing request")
    data = requests.post(basename + f"/channels/{channel_id}/typing",
                         headers={"Authorization": token})

