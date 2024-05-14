#!/bin/env python3

import webbrowser
import threading
import readline
import getpass
import curses
import pyclip
import time
import copy
import api
import sys
import os

api.logging = "--debug-api" in sys.argv
ver = "1.0-dev"

if os.path.isfile("discord_token.txt"):
    token = open("discord_token.txt").readlines()[1].rstrip("\n")
    userid = open("discord_token.txt").readlines()[2].rstrip("\n")
else:
    token = None
    userid = None

def print_help():
    print(" help (h)                      - print this message")
    print(" login (l)                     - interactive login procedure")
    print(" profile (p)                   - print information about your profile")
    print(" listservers (ls)              - list joined servers")
    print(" listchannels (lc) <server id> - list channels on the server")
    print(" interactive (i) <id>          - connect to chat interactively")
    print(" quit (q)                      - quit nahui")

def login():
    global userid, token
    email = input("email: ")
    password = getpass.getpass("password (not echoed): ")
    token, status = api.login(email, password)
    if status[0] == "ok": return
    elif status[0] == "captcha":
        print("discord asks for captcha authentification.\nplease login in the browser:\nhttps://discord.com/app")
    elif status[0] == "bad":
        print("incorrect credentials")
    elif status[0] == "mfa":
        code = input("auth app code: ")
        status = api.mfa_auth(status[1], code)
        if status[0] == "ok": token = status[1]
        elif status[0] == "bad":
            print("incorrect code")
    if token is not None:
        open("discord_token.txt", "w").write("do not share this with anyone\n" + token)
    userid = api.get_user_info(token, "@me")['id']

def profile():
    if not token:
        print("login first")
        return

    i = api.get_user_info(token, "@me")
    p = api.get_profile(token, i['id'])
    print(f"{p['user']['global_name']} ({p['user']['username']})")
    print(f"pronouns: {p['user_profile']['pronouns']}")
    print(f"bio:\n{p['user']['bio']}")

server_cache = None
dm_cache = None
channel_cache = {}

def list_servers(f):
    global server_cache
    if server_cache is None or f: server_cache = api.get_servers(token)
    print("  id  name")
    print("   d  direct messages")
    for k, i in enumerate(server_cache, start=1):
        print(f" {k:>3}  {i['name']}")

def sort_channels(channels):
    categories = sorted(filter(lambda x: x["type"] == 4, channels), key=lambda x: x["position"])
    rchannels = []
    for i in categories:
        rchannels.append(i)
        childs = sorted(filter(lambda x: x["parent_id"] == i["id"], channels), key=lambda x: x["position"])
        rchannels += list(childs)
    return rchannels

def list_channels(server_id, f):
    global server_cache, channel_cache
    if server_cache is None or f: server_cache = api.get_servers(token)
    if server_id not in channel_cache: channel_cache[server_id] = sort_channels(api.get_channels(token, server_cache[server_id]['id']))
    n = 1
    for i in channel_cache[server_id]:
        if i["type"] == 4:
            print("         " + i['name'])
        elif i["type"] == 0: print(f" {server_id+1:>3}:{n:<3}  #" + i['name'])
        elif i["type"] == 2: print(f" {server_id+1:>3}:{n:<3}  " + i['name'])
        else: print(f" {server_id+1:>3}:{n:<3}  " + i['name'])
        n += 1

def list_dms(f):
    global dm_cache
    if dm_cache is None or f: dm_cache = sorted(api.get_dms(token), key=lambda x: int(x['last_message_id'] if 'last_message_id' in x and x['last_message_id'] is not None else x['id']))
    for k, i in enumerate(dm_cache, start=1):
        if i["type"] == 1:
            r = i["recipients"][0]
            if r["global_name"] is None: print(f"   d:{k:<3} {r['username']}")
            else: print(f"   d:{k:<3} {r['global_name']} ({r['username']})")
        elif i["type"] == 3:
            name = i["name"] if i["name"] is not None else "group"
            print(f"   d:{k:<3} {name}")
            for j in i["recipients"]:
                print(f"          {j['global_name']} ({j['username']})")
        else: print("WHAAT")

def isint(string):
    try:
        int(string)
        return True
    except ValueError:
        return False

messages_cache = {}

def split(text, ln):
    res = []
    buf = ""
    n = 0
    for i in text:
        if i == "\n" or n > ln:
            n = 0
            res.append(buf)
            buf = ""
        if i == "\n": continue
        buf += i
        n += 1
    res.append(buf)
    return res

msgs = 0
msgs_lim = 500

msglines = []

def debug_print(*args, sep=" ", end="\n"):
    if "--debug" in sys.argv: open("debug.txt", "a").write(sep.join(map(str, args)) + end)

def draw_chat(scr, channel, mode, sel_msg, render_window, attachment_sel):
    global msgs, msglines, messages_cache
    if len(messages_cache[channel['id']]) == 0:
        scr.addstr(curses.LINES-2, 0, "no messages. maybe start a conversation?")
        return
    
    msglines = []
    buf = []

    for k, i in enumerate((messages_cache[channel['id']])):
        subbuf = []
        author_str = ((">" if sel_msg == k and attachment_sel is None else " ") if mode == 2 else "") + f" {i['author']['username']}: "
        blank_author_str = len(author_str) * " "
        content = i["content"]
        if 'referenced_message' in i and i['referenced_message'] is not None:
            content = f"@{i['referenced_message']['author']['username']} " + content
        slen = curses.COLS-len(author_str)-1
        cp = split(content, slen)
        
        for k1, j in enumerate(cp):
            if k1 == 0: subbuf.append(f"{author_str}{j}")
            else: subbuf.append(f"{blank_author_str}{j}")

        if len(i['attachments']) > 0:
            subbuf.append("   attachments:")
            for k1, j in enumerate(i['attachments']):
                if attachment_sel is not None and attachment_sel[0] == k:
                    if attachment_sel[1] == k1: subbuf.append(f"   > {j['filename']}")
                    else: subbuf.append(f"   | {j['filename']}")
                else: subbuf.append(f"     {j['filename']}")
        msglines.append(len(subbuf))
        buf += subbuf[::-1]

    for k, i in enumerate(buf[render_window:render_window+curses.LINES-2]):
        scr.addstr(curses.LINES-k-2, 0, i)

    if mode == 2:
        if attachment_sel is None:
            scr.addstr(curses.LINES-1, 0, "[^] [v]; [r]eply, [a]ttachments")
        else:
            scr.addstr(curses.LINES-1, 0, "[^] [v]; [o]pen, [c]opy url")

def construct_channel_label(channel):
    length = curses.COLS-2
    start = (('#' if channel['type'] == 0 else '') + channel['name']) if 'name' in channel else channel["recipients"][0]["username"] 
    end = channel['topic'] if 'topic' in channel and channel['topic'] is not None else ''
    spaces = length - (len(start) + len(end))
    if spaces <= 0: return " " + start
    else: return " " + start + " " * spaces + end

def compute_cursor(msg):
    return sum(msglines[:msg+1])

def update_cursor(cur, direction, render_window, msgs_count):
    global limit
    if 0 <= cur+direction < msgs_count:
        cursor = compute_cursor(cur+direction)
        new_rw = render_window
        if cursor <= render_window:
            new_rw = cursor-1
        elif cursor > render_window+curses.LINES-2:
            new_rw = cursor-curses.LINES+2
        return cur+direction, new_rw
    elif cur+direction < msgs_count:
        limit += 50
    else: return cur, render_window

def clear_status(scr):
    scr.addstr(curses.LINES-1, 0, " " * (curses.COLS-1))
    scr.move(curses.LINES-1, 0)

def get_str(scr):
    clear_status(scr)
    scr.addstr(curses.LINES-1, 0, "~ ")
    string = ""
    ch = scr.get_wch()
    while ch != "\n":
        clear_status(scr)
        if ch == curses.KEY_BACKSPACE: string = string[:-1]
        else: string += ch
        first = (len(string)+1) // (curses.COLS - 1) == 0
        last_str = string[(len(string)+1) // (curses.COLS - 1)*(curses.COLS - 1):]
        scr.addstr(curses.LINES-1, 0, ("~ " if first else "- ") + last_str)
        ch = scr.get_wch()
    return string

limit = 50

def curses_interactive(channel, scr):
    global msgs, keys, update_thread, channel_cache, messages_cache
    curses.noecho()
    curses.curs_set(0)
    scr.nodelay(True)
    mode = 0
    sel_msg = 0
    render_window = 0
    reply = None

    attachment_sel = None

    if channel['id'] in messages_cache:
        old_msgs = messages_cache[channel['id']]
    else:
        old_msgs = None

    scr.clear()
    scr.addstr(0, 0, construct_channel_label(channel))
    old_mode = None
    old_rw = None
    old_sm = None
    old_a = None
    while True:
        if channel['id'] not in messages_cache or messages_cache[channel['id']] is None or msgs > msgs_lim:
            msgs = 0
            messages_cache[channel['id']] = api.get_messages(token, channel['id'], limit=limit)
        
        if messages_cache[channel['id']] != old_msgs or mode != old_mode or render_window != old_rw or sel_msg != old_sm or attachment_sel != old_a:
            scr.clear()
            scr.addstr(0, 0, construct_channel_label(channel))
            draw_chat(scr, channel, mode, sel_msg, render_window, attachment_sel)

        old_mode = mode
        old_rw = render_window
        old_sm = sel_msg
        old_a = copy.copy(attachment_sel)

        msgs += 1
        scr.move(curses.LINES-1, 0)
        key = scr.getch()
        if key == 0x1b:
            if mode == 2:
                mode = 0
                attachment_sel = None
                render_window = sel_msg = 0
            elif mode == 0: break
        if key == curses.KEY_UP and mode == 2:
            if attachment_sel is None:
                sel_msg, render_window = update_cursor(sel_msg, 1, render_window, len(messages_cache[channel['id']]))
            else:
                attachment_sel[1] = (attachment_sel[1] - 1) % len(messages_cache[channel['id']][sel_msg]['attachments'])
        if key == curses.KEY_DOWN and mode == 2:
            if attachment_sel is None:
                sel_msg, render_window = update_cursor(sel_msg, -1, render_window, len(messages_cache[channel['id']]))
            else:
                attachment_sel[1] = (attachment_sel[1] + 1) % len(messages_cache[channel['id']][sel_msg]['attachments'])
        if key == ord("r") and mode == 2:
            reply = sel_msg
            mode = 1
        if key == ord("a") and mode == 2:
            if len(messages_cache[channel['id']][sel_msg]['attachments']) > 0:
                attachment_sel = [sel_msg, 0]
        if key == ord("q") and mode == 0: break
        if key == ord("i") and mode == 0:
            mode = 1
            api.typing(token, channel['id'])
        if key == ord("s") and mode == 0:
            mode = 2
            render_window = 0
            sel_msg = 0
        if key == ord("o") and mode == 2 and attachment_sel is not None:
            webbrowser.open(messages_cache[channel['id']][sel_msg]['attachments'][attachment_sel[1]]['url'])
        if key == ord("c") and mode == 2 and attachment_sel is not None:
            pyclip.copy(messages_cache[channel['id']][sel_msg]['attachments'][attachment_sel[1]]['url'])
        
        if mode == 1:
            scr.nodelay(False)
            curses.curs_set(1)
            curses.echo()
            message = get_str(scr)
            curses.noecho()
            clear_status(scr)
            mode = 0
            curses.curs_set(0)
            api.send_message(token, channel['id'], message, reply=(channel['id'], channel['guild_id'], messages_cache[channel['id']][reply]['id']) if reply is not None else None)
            reply = None
            scr.nodelay(True)
        #scr.refresh()
        curses.update_lines_cols()
        old_msgs = messages_cache[channel['id']]
        #time.sleep(1/2)

def interactive(chat, f):
    global dm_cache, server_cache, channel_cache
    
    if ":" not in chat or len(chat) < 3:
        print("invalid chat id (no colon)")
        return

    server_id, chat_id = chat.split(":")
    if not ((isint(server_id) or server_id == "d") and isint(chat_id)):
        print("invalid chat id (NaN)")
        return

    if server_id == "d":
        if dm_cache is None or f: dm_cache = sorted(api.get_dms(token), key=lambda x: int(x['last_message_id'] if 'last_message_id' in x and x['last_message_id'] is not None else x['id']))
        dcid = dm_cache[int(chat_id)-1]
    else:
        if server_cache is None or f: server_cache = api.get_servers(token)
        if server_id not in channel_cache: channel_cache[server_id] = sort_channels(api.get_channels(token, server_cache[int(server_id)-1]['id']))
        dcid = channel_cache[server_id][int(chat_id)-1]
        if dcid["type"] == 4:
            print("you cant chat in category")
            return

    curses.wrapper(lambda x: curses_interactive(dcid, x))

if __name__ == "__main__":
    print(f"welcome to cadmium, version {ver}")
    while True:
        try: command = input("> ").split()
        except KeyboardInterrupt: exit()
        except EOFError: exit()
        if len(command) == 0: continue
        f = False
        if "f" in command: f = True

        if command[0] in ("help", "h"): print_help()
        elif command[0] in ("login", "l"): login()
        elif command[0] in ("profile", "p"): profile()
        elif command[0] in ("listservers", "ls"): list_servers(f)
        elif command[0] in ("listchannels", "lc"):
            if command[1] == 'd': list_dms(f)
            else: list_channels(int(command[1])-1, f)
        elif command[0] in ("interactive", "i"): interactive(command[1], f)
        elif command[0] in ("quit", "q"): exit()
        else: print("unknown command, refer to `help`")

