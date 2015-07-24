import traceback
import sys, os
import praw, oauthPS2Bot
import time
import sqlite3
import re
import json
import requests
from datetime import datetime,timedelta

URL_CENSUS_CHAR = 'http://census.daybreakgames.com/s:vAPP/get/ps2:v2/character/?name.first=%s&c:case=false&c:resolve=stat_history,faction,world,outfit_member_extended'
URL_CENSUS_CHAR_STAT = 'http://census.daybreakgames.com/s:vAPP/get/ps2:v2/characters_stat?character_id=%s&c:limit=5000'

URL_DASANFALL = "[[dasanfall]](http://stats.dasanfall.com/ps2/player/%s)"
URL_FISU = "[[fisu]](http://ps2.fisu.pw/player/?name=%s)"
URL_PSU = "[[psu]](http://www.planetside-universe.com/character-%s.php)"
URL_PLAYERS = "[[players]](https://www.planetside2.com/players/#!/%s)"
URL_KILLBOARD = "[[killboard]](https://www.planetside2.com/players/#!/%s/killboard)"

USERNAME = "ps2bot"

SERVERS = {
    '1': 'Connery (US West)',
    '17': 'Emerald (US East)',
    '10': 'Miller (EU)',
    '13': 'Cobalt (EU)',
    '25': 'Briggs (AU)',
    '19': 'Jaeger'
}

POST_REPLY_TEMPLATE = '''
**Some stats about {char_name_truecase}.**

------

- Character created: {char_creation}
- Last login: {char_login}
- Time played: {char_playtime} ({char_logins} login{login_plural})
- Battle rank: {char_rank}
- Faction: {char_faction_en}
- Server: {char_server}
- Outfit: {char_outfit}
- Score: {char_score} | Captured: {char_captures} | Defended: {char_defended}
- Medals: {char_medals} | Ribbons: {char_ribbons} | Certs: {char_certs}
- Kills: {char_kills} | Assists: {char_assists} | Deaths: {char_deaths} | KDR: {char_kdr}
- Links: {links_dasanfall} {links_fisu} {links_psu} {links_players} {links_killboard}

------

^^This ^^post ^^was ^^made ^^by ^^a ^^bot.
^^Have ^^feedback ^^or ^^a ^^suggestion?
[^^\[pm ^^the ^^creator\]]
(https://np.reddit.com/message/compose/?to=microwavable_spoon&subject=PS2Bot%20Feedback)
^^| [^^\[see ^^my ^^code\]](https://github.com/plasticantifork/PS2Bot)
'''

sql = sqlite3.connect((os.path.join(sys.path[0],'ps2bot-sql.db')))
cur = sql.cursor()

cur.execute('CREATE TABLE IF NOT EXISTS oldmentions(id TEXT)')
cur.execute('CREATE INDEX IF NOT EXISTS mentionindex on oldmentions(id)')
sql.commit()

r = oauthPS2Bot.login()

def now_stamp():
    psttime = datetime.utcnow() - timedelta(hours=7)
    time_stamp = psttime.strftime("%m-%d-%y %I:%M:%S %p PST ::")
    return time_stamp

def generate_report(charname, mid):
    try:
        census_char = requests.get(URL_CENSUS_CHAR % charname)
    except (IndexError, HTTPError):
        return None
        
    census_char = census_char.text
    census_char = json.loads(census_char)
    char_exist = census_char['returned']
    if char_exist != 1:
        print('%s %s - character: %s does not exist. Adding to database anyway (003)' % (now_stamp(), mid, charname))
        cur.execute('INSERT INTO oldmentions VALUES(?)', [mid])
        sql.commit()
        return None
            
    census_char = census_char['character_list'][0]
    char_name_truecase = census_char['name']['first']
    char_id = census_char['character_id']
    try:
        census_stat = requests.get(URL_CENSUS_CHAR_STAT % char_id)
    except (IndexError, HTTPError):
        return None
        
    time_format = "%a, %b %d, %Y (%m/%d/%y), %I:%M:%S %p PST"
    char_creation = time.strftime(time_format, time.localtime(float(census_char['times']['creation'])))
    char_login = time.strftime(time_format, time.localtime(float(census_char['times']['last_login'])))
    char_login_count = int(float(census_char['times']['login_count']))
    char_hours, char_minutes = divmod(int(census_char['times']['minutes_played']), 60)
    
    char_playtime = "{:,} hour{s}".format(char_hours, s='' if char_hours == 1 else 's')
    char_playtime += " {:,} minute{s}".format(char_minutes, s='' if char_minutes == 1 else 's')

    try:
        char_score = int(census_char['stats']['stat_history'][8]['all_time'])
        char_capture = int(census_char['stats']['stat_history'][3]['all_time'])
        char_defend = int(census_char['stats']['stat_history'][4]['all_time'])
        char_medal = int(census_char['stats']['stat_history'][6]['all_time'])
        char_ribbon = int(census_char['stats']['stat_history'][7]['all_time'])
        char_certs = int(census_char['stats']['stat_history'][1]['all_time'])
    except (IndexError, KeyError, ValueError):
        char_score = 0
        char_capture = 0
        char_defend = 0
        char_medal = 0
        char_ribbon = 0
        char_certs = 0

    char_rank = '%s' % census_char['battle_rank']['value']
    char_rank_next = census_char['battle_rank']['percent_to_next']
    if char_rank_next != "0":
        char_rank += " (%s%% to next)" % char_rank_next

    char_faction = census_char['faction']
    try:
        char_outfit = census_char['outfit_member']
        if char_outfit['member_count'] != "1":
            members = '{:,}'.format(int(char_outfit['member_count']))
            char_outfit = '[%s] %s (%s members)' % (char_outfit['alias'], char_outfit['name'], members)
        else:
            char_outfit = '[%s] %s (1 member)' % (char_outfit['alias'], char_outfit['name'])
    except KeyError:
        char_outfit = "None"

    try:
        char_kills = int(census_char['stats']['stat_history'][5]['all_time'])
        char_deaths = int(census_char['stats']['stat_history'][2]['all_time'])
        if char_deaths != 0:
            char_kdr = round(char_kills/char_deaths,3)
        else:
            char_kdr = char_kills
    except (KeyError, ZeroDivisionError):
        char_kills = 0
        char_deaths = 0
        char_kdr = 0
    census_stat = census_stat.text
    census_stat = json.loads(census_stat)
    char_stat = census_stat['characters_stat_list']
    try:
        for stat in char_stat:
            if stat['stat_name'] == 'assist_count':
                char_assists = int(stat['value_forever'])
                break
            else:
                char_assists = 0
    except (IndexError, KeyError, ValueError):
        char_assists = 0
        
    post_reply = POST_REPLY_TEMPLATE.format(
        char_name_truecase = char_name_truecase,
        char_creation = char_creation,
        char_login = char_login,
        char_playtime = char_playtime,
        char_logins = '{:,}'.format(char_login_count),
        login_plural = 's' if char_login_count != 1 else '',
        char_rank = char_rank,
        char_faction_en = char_faction['name']['en'],
        char_server = SERVERS[census_char['world_id']],
        char_outfit = char_outfit,
        char_score = '{:,}'.format(char_score),
        char_captures ='{:,}'.format(char_capture),
        char_defended = '{:,}'.format(char_defend),
        char_medals = '{:,}'.format(char_medal),
        char_ribbons = '{:,}'.format(char_ribbon),
        char_certs = '{:,}'.format(char_certs),
        char_kills = '{:,}'.format(char_kills),
        char_assists = '{:,}'.format(char_assists),
        char_deaths = '{:,}'.format(char_deaths),
        char_kdr = '{:,}'.format(char_kdr),
        links_dasanfall = URL_DASANFALL % char_id,
        links_fisu = URL_FISU % char_name_truecase,
        links_psu = URL_PSU % char_id,
        links_players = URL_PLAYERS % char_id,
        links_killboard = URL_KILLBOARD % char_id
        )
    return post_reply

def ps2bot():
    mentions = []
    unreads = list(r.get_unread(limit=None))
    for unread in unreads:
        if ('u/'+USERNAME) in unread.body.lower():
            mentions.append(unread)
        else:
            unread.mark_as_read()
    for mention in mentions:
        mention.mark_as_read()
        mid = mention.id
        
        try:
            pauthor = mention.author.name
        except AttributeError:
            continue

        if pauthor.lower() == USERNAME:
            continue

        cur.execute('SELECT * FROM oldmentions WHERE ID=?', [mid])
        if cur.fetchone():
            continue
        
        pbody = mention.body.lower()
        pbody = pbody.replace('\n', ' ')
        pbody_split = pbody.split('/')
        pbody_split = re.sub(r'[^A-Za-z0-9 ]+', '', str(pbody_split))
        pbody_split = pbody_split.split(' ')
        pbody_split = list(filter(None, pbody_split))
        try:
            if pbody_split.index(USERNAME) == (len(pbody_split)-1):
                print('%s %s is not valid. Adding to database anyway. (001)' % (now_stamp(), mid))
                cur.execute('INSERT INTO oldmentions VALUES(?)', [mid])
                sql.commit()
                continue
            else:
                try:
                    charname = ""
                    pbody_index = 0
                    while 1:
                        pbody_index = pbody_split.index(USERNAME, pbody_index+1)
                        if pbody_split[pbody_index-1] == "u":
                            charname = pbody_split[pbody_index+1]
                except ValueError:
                    pass
                if charname == "":
                    print('%s %s is not valid. Adding to database anyway. (001)' % (now_stamp(), mid))
                    cur.execute('INSERT INTO oldmentions VALUES(?)', [mid])
                    sql.commit()
                    continue
        except (IndexError, KeyError):
            print('%s %s is not valid. Adding to database anyway. (002)' % (now_stamp(), mid))
            cur.execute('INSERT INTO oldmentions VALUES(?)', [mid])
            sql.commit()
            continue
        
        cur.execute('INSERT INTO oldmentions VALUES(?)', [mid])
        sql.commit()

        post_reply = generate_report(charname, mid)
        if post_reply is None:
            continue

        print('%s Replying to %s by %s' % (now_stamp(), mid, pauthor))
        try:
            mention.reply(post_reply)
        except APIException:
            pass

try:
    ps2bot()
except requests.exceptions.HTTPError:
    print(now_stamp(), 'A site/service is down. Probably Reddit.')
except Exception:
    traceback.print_exc()
quit()
