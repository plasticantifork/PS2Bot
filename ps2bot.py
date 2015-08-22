###############################################################################
### PS2Bot (running at https://www.reddit.com/user/PS2Bot)
### Github https://github.com/plasticantifork/PS2Bot
### By /u/microwavable_spoon (aka plasticantifork)
### With contributions from /u/shaql & /u/GoldenSights
###############################################################################

import json
import praw
import oauthPS2Bot
import os
import re
import requests
import shlex
import sqlite3
import sys
import time
import traceback
from datetime import datetime,timedelta
import warnings
warnings.filterwarnings('ignore')

censusCharPC = 'http://census.daybreakgames.com/s:vAPP/get/ps2:v2/character/?name.first=%s&c:case=false&c:resolve=stat_history,faction,world,outfit_member_extended'
censusCharPS4US = 'http://census.daybreakgames.com/s:vAPP/get/ps2ps4us:v2/character/?name.first=%s&c:case=false&c:resolve=stat_history,faction,world,outfit_member_extended'
censusCharPS4EU = 'http://census.daybreakgames.com/s:vAPP/get/ps2ps4eu:v2/character/?name.first=%s&c:case=false&c:resolve=stat_history,faction,world,outfit_member_extended'

censusCharStatPC = 'http://census.daybreakgames.com/s:vAPP/get/ps2:v2/characters_stat?character_id=%s&c:limit=5000'
censusCharStatPS4US = 'http://census.daybreakgames.com/s:vAPP/get/ps2ps4us:v2/characters_stat?character_id=%s&c:limit=5000'
censusCharStatPS4EU = 'http://census.daybreakgames.com/s:vAPP/get/ps2ps4eu:v2/characters_stat?character_id=%s&c:limit=5000'

censusServerStatus = 'https://census.daybreakgames.com/s:vAPP/json/status?game=ps2'

externalStatsDasanfall = '[[dasanfall]](http://stats.dasanfall.com/ps2/player/%s)'
externalStatsFisu = '[[fisu]](http://ps2.fisu.pw/player/?name=%s)'
externalStatsFisuPS4US = '[[fisu]](http://ps4us.ps2.fisu.pw/player/?name=%s)'
externalStatsFisuPS4EU = '[[fisu]](http://ps4eu.ps2.fisu.pw/player/?name=%s)'
externalStatsPsu = '[[psu]](http://www.planetside-universe.com/character-%s.php)'
externalStatsPlayers = '[[players]](https://www.planetside2.com/players/#!/%s)'
externalStatsKillboard = '[[killboard]](https://www.planetside2.com/players/#!/%s/killboard)'

serverDict = {
    '1': 'Connery (US West)',
    '17': 'Emerald (US East)',
    '10': 'Miller (EU)',
    '13': 'Cobalt (EU)',
    '25': 'Briggs (AU)',
    '19': 'Jaeger',
    '1000': 'Genudine',
    '1001': 'Palos',
    '1002': 'Crux',
    '2000': 'Ceres',
    '2001': 'Lithcorp'
}

replyTextTemplate = '''
**Some stats about {charCase} ({gameVersion}).**

---

- Character created: {charCreation}
- Last login: {charLogin}
- Time played: {charPlaytime} ({charLogins} login{loginPlural})
- Battle rank: {charRank}
- Faction: {charFaction}
- Server: {charServer}
- Outfit: {charOutfit}
- Score: {charScore} | Captured: {charCaptured} | Defended: {charDefended}
- Medals: {charMedals} | Ribbons: {charRibbons} | Certs: {charCerts}
- Kills: {charKills} | Assists: {charAssists} | Deaths: {charDeaths} | KDR: {charKDR}
- Links: {externalStats}


'''

replyTextFooter = '''

---

^^This ^^post ^^was ^^made ^^by ^^a ^^bot.
^^Have ^^feedback ^^or ^^a ^^suggestion?
[^^\[pm ^^the ^^creator\]]
(https://np.reddit.com/message/compose/?to=microwavable_spoon&subject=PS2Bot%20Feedback)
^^| [^^\[see ^^my ^^code\]](https://github.com/plasticantifork/PS2Bot)
'''

commandIdentifiers = ['/u/ps2bot', 'u/ps2bot']
multipleCommandJoiner = '\n---\n'

sql = sqlite3.connect((os.path.join(sys.path[0],'ps2bot-sql.db')))
cur = sql.cursor()

cur.execute('CREATE TABLE IF NOT EXISTS oldmentions(id TEXT)')
cur.execute('CREATE INDEX IF NOT EXISTS mentionindex on oldmentions(id)')
sql.commit()

r = oauthPS2Bot.login()

def nowStamp():
    pstTime = datetime.utcnow() - timedelta(hours=7)
    timeStamp = pstTime.strftime('%m-%d-%y %I:%M:%S %p PST ::')
    return timeStamp

def generateReportPC(charName=None, *trash):
    if charName is None:
        return
    externalStats = [
    {'url': externalStatsDasanfall, 'identifier': 'char_id'},
    {'url': externalStatsFisu, 'identifier': 'char_name'},
    {'url': externalStatsPsu, 'identifier': 'char_id'},
    {'url': externalStatsPlayers, 'identifier': 'char_id'},
    {'url': externalStatsKillboard, 'identifier': 'char_id'}
    ]
    return generateReport(charName, censusCharPC, censusCharStatPC, externalStats, 'PC')

def generateReportPS4US(charName=None, *trash):
    if charName is None:
        return
    externalStats = [
    {'url': externalStatsFisuPS4US, 'identifier': 'char_name'}
    ]
    return generateReport(charName, censusCharPS4US, censusCharStatPS4US, externalStats, 'PS4 US')

def generateReportPS4EU(charName=None, *trash):
    if charName is None:
        return
    externalStats = [
    {'url': externalStatsFisuPS4EU, 'identifier': 'char_name'}
    ]
    return generateReport(charName, censusCharPS4EU, censusCharStatPS4EU, externalStats, 'PS4 EU')

def reportServerStatus(*trash):
    statusStatusDict = {'low': 'UP','medium': 'UP','high': 'UP','down': 'DOWN'}
    statusRegionsDict = {'Palos': 'Palos (US)','Genudine': 'Genudine (US)','Crux': 'Crux (US)'}
    statusPopulationDict = {'down': ''}
    jContent = json.loads(requests.get(censusServerStatus).text)
    results = []
    
    def statusReader(jInfo, header):
        table = []
        entries = []
        table.append(header)
        table.append('server | status | population')
        table.append(':- | :-: | :-:')

        for server, status in jInfo.items():
            if any(nonexist in server for nonexist in ['Dahaka', 'Xelas', 'Rashnu', 'Searhus']):
                continue
            server = statusRegionsDict.get(server, server)
            pop = status['status']
            updown = statusStatusDict[pop]
            pop = statusPopulationDict.get(pop, pop)
            entries.append('%s | %s | %s' % (server, updown, pop))

        entries.sort(key=lambda x: ('(US W' in x, '(US E' in x, '(US' in x, '(EU' in x, '(AU' in x, x), reverse=True)
        table += entries
        table.append('\n\n')
        return table

    results += statusReader(jContent['ps2']['Live'], '**PC Server Status**\n')
    results += statusReader(jContent['ps2']['Live PS4'], '**PS4 Server Status**\n')
    results = '\n'.join(results)
    return results

def generateReport(charName, urlCensus, urlStatistics, externalStats, gameVersion):
    try:
        censusChar = requests.get(urlCensus % charName)
        censusChar = censusChar.text
        censusChar = json.loads(censusChar)
    except (IndexError, KeyError, requests.exceptions.HTTPError):
        return None

    if censusChar['returned'] != 1:
        print('%s Character %s does not exist' % (nowStamp(), charName))
        return
            
    censusChar = censusChar['character_list'][0]
    charCase = censusChar['name']['first']
    charID = censusChar['character_id']
    try:
        censusStat = requests.get(urlStatistics % charID)
        censusStat = censusStat.text
        censusStat = json.loads(censusStat)
        if censusStat['returned'] == 0:
            print('%s Character %s has never logged on' % (nowStamp(), charName))
            return
    except (IndexError, KeyError, requests.exceptions.HTTPError):
        return
        
    timeFormat = '%a, %b %d, %Y (%m/%d/%y), %I:%M:%S %p PST'
    charCreation = time.strftime(timeFormat, time.localtime(float(censusChar['times']['creation'])))
    charLogin = time.strftime(timeFormat, time.localtime(float(censusChar['times']['last_login'])))
    charLoginCount = int(float(censusChar['times']['login_count']))
    charHours, charMinutes = divmod(int(censusChar['times']['minutes_played']), 60)
    
    charPlaytime = '{:,} hour{s}'.format(charHours, s='' if charHours == 1 else 's')
    charPlaytime += ' {:,} minute{s}'.format(charMinutes, s='' if charMinutes == 1 else 's')

    try:
        charScore = int(censusChar['stats']['stat_history'][8]['all_time'])
    except (IndexError, KeyError, ValueError):
        charScore = 0
    try:
        charCaptured = int(censusChar['stats']['stat_history'][3]['all_time'])
    except (IndexError, KeyError, ValueError):
        charCaptured = 0
    try:
        charDefended = int(censusChar['stats']['stat_history'][4]['all_time'])
    except (IndexError, KeyError, ValueError):
        charDefended = 0
    try:
        charMedals = int(censusChar['stats']['stat_history'][6]['all_time'])
    except (IndexError, KeyError, ValueError):
        charMedals = 0
    try:
        charRibbons = int(censusChar['stats']['stat_history'][7]['all_time'])
    except (IndexError, KeyError, ValueError):
        charRibbons = 0
    try:
        charCerts = int(censusChar['stats']['stat_history'][1]['all_time'])
    except (IndexError, KeyError, ValueError):
        charCerts = 0

    charRank = '%s' % censusChar['battle_rank']['value']
    charRankNext = censusChar['battle_rank']['percent_to_next']
    if charRankNext != '0':
        charRank += ' (%s%% to next)' % charRankNext

    charFaction = censusChar['faction']
    try:
        charOutfit = censusChar['outfit_member']
        if charOutfit['member_count'] != '1':
            members = '{:,}'.format(int(charOutfit['member_count']))
            charOutfit = '[%s] %s (%s members)' % (charOutfit['alias'], charOutfit['name'], members)
        else:
            charOutfit = '[%s] %s (1 member)' % (charOutfit['alias'], charOutfit['name'])
    except KeyError:
        charOutfit = 'None'

    try:
        charKills = int(censusChar['stats']['stat_history'][5]['all_time'])
        charDeaths = int(censusChar['stats']['stat_history'][2]['all_time'])
        if charDeaths != 0:
            charKDR = round(charKills/charDeaths,3)
        else:
            charKDR = charKills
    except (KeyError, ZeroDivisionError):
        charKills = 0
        charDeaths = 0
        charKDR = 0

    charStat = censusStat['characters_stat_list']
    #print(charStat)
    charAssists = 0
    try:
        for stat in charStat:
            if stat['stat_name'] == 'assist_count':
                charAssists = int(stat['value_forever'])
                break
    except (IndexError, KeyError, ValueError):
        charAssists = 0
        
    filledExternalStats = []
    for site in externalStats:
        url = site['url']
        if site['identifier'] == 'char_id':
            url = url % charID
        elif site['identifier'] == 'char_name':
            url = url % charCase
        filledExternalStats.append(url)
    filledExternalStats = ' '.join(filledExternalStats)

    replyText = replyTextTemplate.format(
        charCase = charCase,
        gameVersion = gameVersion,
        charCreation = charCreation,
        charLogin = charLogin,
        charPlaytime = charPlaytime,
        charLogins = '{:,}'.format(charLoginCount),
        loginPlural = 's' if charLoginCount != 1 else '',
        charRank = charRank,
        charFaction = charFaction['name']['en'],
        charServer = serverDict[censusChar['world_id']],
        charOutfit = charOutfit,
        charScore = '{:,}'.format(charScore),
        charCaptured ='{:,}'.format(charCaptured),
        charDefended = '{:,}'.format(charDefended),
        charMedals = '{:,}'.format(charMedals),
        charRibbons = '{:,}'.format(charRibbons),
        charCerts = '{:,}'.format(charCerts),
        charKills = '{:,}'.format(charKills),
        charAssists = '{:,}'.format(charAssists),
        charDeaths = '{:,}'.format(charDeaths),
        charKDR = '{:,}'.format(charKDR),
        externalStats = filledExternalStats
        )
    return replyText

def handleBotMention(mention, *trash):
    #print('handling mention', mention.id)
    mention.mark_as_read()
        
    try:
        pAuthor = mention.author.name
    except AttributeError:
        return

    cur.execute('SELECT * FROM oldmentions WHERE ID=?', [mention.id])
    if cur.fetchone():
        return
        
    cur.execute('INSERT INTO oldmentions VALUES(?)', [mention.id])
    sql.commit()

    replyText = functionMapComment(mention.body)

    if replyText in [[], None]:
        return

    replyText = multipleCommandJoiner.join(replyText)
    replyText += replyTextFooter
    #print('Generated reply text:', replyText[:10])

    print('%s Replying to %s by %s' % (nowStamp(), mention.id, pAuthor))
    try:
        mention.reply(replyText)
    except praw.errors.PRAWException:
        return

def functionMapLine(text):
    #print('User said:', text)
    elements = shlex.split(text)
    #print('Broken into:', elements)
    results = []
    for elementIndex, element in enumerate(elements):
        if element.lower() not in commandIdentifiers:
            continue

        arguments = elements[elementIndex:]
        assert arguments.pop(0).lower() in commandIdentifiers
        
        # process one command per line at a time
        for argumentIndex, argument in enumerate(arguments):
            if argument.lower() in commandIdentifiers:
                arguments = arguments[:argumentIndex]
                break

        #print('Found command:', arguments)
        if len(arguments) == 0:
            #print('Did nothing')
            continue

        command = arguments[0].lower()
        actualFunction = command in functionMap
        function = functionMap.get(command, defaultFunction)
        #print('Using function:', function.__name__)

        if actualFunction:
            arguments = arguments[1:]
        result = function(*arguments)
        #print('Output:', result)
        results.append(result)
    return results

def functionMapComment(comment):
    lines = comment.split('\n')
    results = []
    for line in lines:
        result = functionMapLine(line)
        if result is None:
            continue
        result = list(filter(None, result))
        if result is []:
            continue
        results += result
        
    # remove duplicate commands
    results.reverse()
    for item in results[:]:
        if results.count(item) > 1:
            results.remove(item)
    results.reverse()
            
    return results

def ps2bot():
    unreads = list(r.get_unread(limit=None))
    for message in unreads:
        if ('u/ps2bot') in message.body.lower():
            handleBotMention(message)
        else:
            message.mark_as_read()

defaultFunction = generateReportPC
functionMap = {
    '!player': generateReportPC,
    '!p': generateReportPC,

    '!playerps4us': generateReportPS4US,
    '!ps4us': generateReportPS4US,
    '!p4us': generateReportPS4US,

    '!playerps4eu': generateReportPS4EU,
    '!ps4eu': generateReportPS4EU,
    '!p4eu': generateReportPS4EU,

    '!status': reportServerStatus,
    '!s': reportServerStatus
}
functionMap = {c.lower():functionMap[c] for c in functionMap}

try:
    ps2bot()
except praw.errors.HTTPException:
    pass
except Exception:
    traceback.print_exc()
