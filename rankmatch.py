import csv, re, copy
from datetime import datetime
from collections import OrderedDict, defaultdict

def addTo(event, group):
    event["open"] -= len(group["team_numbers"])
    event["groups"].append(group)
    
def removeFrom(event, group):
    event["open"] += len(group["team_numbers"])
    event["groups"].remove(group)
    
def pushAll(src, pushable):
    for target, pushee in pushable:
        if target["open"] >= len(pushee["team_numbers"]):
            removeFrom(src, pushee)
            addTo(target, pushee)
            break

def tryPushTo(events, event, group, pushLimit):
    for ev in events.values():
        ev["shadow_open"] = ev["open"]
    pushable = []
    avail = event["open"]
    pushees = sorted(event["groups"], key=lambda g: g["date"], reverse=True)
    for rank in range(pushLimit+1):
        # Displace people to underfilled events
        for pushee in copy.copy(pushees):
            sel = events[pushee["selections"][rank]]
            filled = sel["max"]-sel["open"]
            if sel == event: continue
            if filled < sel["min"] and sel["shadow_open"] >= len(pushee["team_numbers"]):
                pushable.append([sel, pushee])
                pushees.remove(pushee)
                avail += len(pushee["team_numbers"])
                sel["shadow_open"] -= len(pushee["team_numbers"])
                if avail >= len(group["team_numbers"]):
                    pushAll(event, pushable)
                    addTo(event, group)
                    return True

        # Displace people to open events
        for pushee in copy.copy(pushees):
            sel = events[pushee["selections"][rank]]
            filled = sel["max"]-sel["open"]
            if sel == event: continue
            if sel["shadow_open"] >= len(pushee["team_numbers"]):
                pushable.append([sel, pushee])
                pushees.remove(pushee)
                avail += len(pushee["team_numbers"])
                sel["shadow_open"] -= len(pushee["team_numbers"])
                if avail >= len(group["team_numbers"]):
                    pushAll(event, pushable)
                    addTo(event, group)
                    return True
    return False

def pushPass(events, groups, rank):
    for group in copy.copy(groups):
        event = events[group["selections"][rank]]
        if tryPushTo(events, event, group, rank):
            groups.remove(group)

def allocationPass(events, groups, rank):
    for group in copy.copy(groups):
        event = events[group["selections"][rank]]
        if event["open"] >= len(group["team_numbers"]):
            addTo(event, group)
            groups.remove(group)


    
def getSchedule(events, groups):
    # events = {
    #    "Waterloo - 08/17": {
    #       "max": 30,
    #       "open": 30,
    #       "min": 8,
    #       "groups": []
    #    },
    #    ...
    # }
    
    # groups = [
    #   {
    #      "teams": [1114, 2056, ...],
    #      "date": Date(2014, 8, 10),
    #      "selections": ["waterloo", "GTR-east", ...]
    #      "current": 1
    #   },
    #   ...
    # ]
    failed = []

    groups.sort(key=lambda g: g["date"])

    allocationPass(events, groups, 0)
    allocationPass(events, groups, 1)
    pushPass(events, groups, 1)
    allocationPass(events, groups, 2)
    pushPass(events, groups, 2)

    # Everything left failed
    events["Unmatched"] = {"groups": groups, "max": "0", "min": 0, "open": 0, "total": 0}
            
    return events


def numericSort(n):
    return str(len(n))+n

def getHeader(headers, pattern):
    index = None
    for i, h in enumerate(headers):
        if re.search(pattern, h, re.IGNORECASE):
            if index is not None: raise IOError('Multiple columns matching: "'+pattern+'"')
            index = i
    if index is not None:
        return index
    else:
        raise IOError('No column matching: "'+pattern+'"')

def utfStrip(str):
    return re.sub(r'[^\x00-\x7F]+','', str)


def rankMatch(src_events, src_data):
    errors = []

# Parse CSV to events
    events = {}
    for row in src_events[1:]:
        spots = int(row[1])
        name = utfStrip(row[0])
        extra = 0 if spots<=12 else 1 if spots<=20 else 2
        events[name] = {
            "groups": [],
            "total": spots,
            "max": spots-extra,
            "open": spots-extra,
            "min": 8,
        }
    
# Parse CSV to teams
    teamIndex = {}
    headers = src_data[0]
    TEAM_NUMBER = getHeader(headers, r'team #')
    CHOICE1 = getHeader(headers, r'1st choice')
    CHOICE2 = getHeader(headers, r'2nd choice')
    CHOICE3 = getHeader(headers, r'3rd choice')
    FRIENDS = getHeader(headers, r'team paired')
    PRIORITY = getHeader(headers, r'preference')
    DATE = getHeader(headers, r'startdate')

    for i, row in list(enumerate(src_data))[1:]:
        row += [""]*(len(headers) - len(row)) # pad
        m = re.search("\d\d\d+", row[TEAM_NUMBER])
        number = m.group() if m else ""
        try:
            date = datetime.strptime(row[DATE], "%m-%d-%Y")
        except:
            errors.append(["error", "Row #"+str(i+1)+" has an invalid date. WILL BE SKIPPED!"])
            continue

        if not row[CHOICE1] or not row[CHOICE2] or not row[CHOICE3]:
            errors.append(["error", "Row #"+str(i+1)+" (team "+row[TEAM_NUMBER]+") is missing selections for 1st, 2nd and/or 3rd place. WILL BE SKIPPED!"])
            continue

        if not number:
            errors.append(["error", "Row #"+str(i+1)+' is missing a team number, has "'+row[TEAM_NUMBER]+'" instead. WILL BE SKIPPED!'])
            continue

        team = {
            "index": i,
            "date": date,
            "number": row[TEAM_NUMBER].strip(),
            "selections": [
                utfStrip(row[CHOICE1]), 
                utfStrip(row[CHOICE2]),
                utfStrip(row[CHOICE3])
            ],
            "friends": set(re.findall(r'\d\d\d+', row[FRIENDS])),
            "priority": bool(row[PRIORITY])
        }
        teamIndex[number] = team


# Sort and error check teams
    teams = OrderedDict()

    for team_number in sorted(teamIndex.keys(), key=numericSort):
        teams[team_number] = teamIndex[team_number]
        
    for team_number, team in teams.items():
        if team_number in team["friends"]:
            errors.append(["warning", "Team #"+team_number+" tried to add themselves. This will be ignored."])
            team["friends"].remove(team_number)
        if len(set(team["selections"])) < 3:
            errors.append(["warning", "Team #"+team_number+" selected the same event more than once. This will be ignored."])
    

# Organize teams into groups
    groups = []
    while teams:
        team_number = teams.keys()[0]
        team = teams.pop(team_number)
        group = {
            "teams": [team],
            "team_numbers": set([team["number"]]),
            "nominees": team["friends"]
        }
        groups.append(group)
        while group["nominees"]:
            for nominee_number in group["nominees"]:
                if nominee_number not in teamIndex:
                    errors.append(["error", "("+", ".join(group["team_numbers"])+", etc.) tried to add team #"+nominee_number+" which is not registered. This will be ignored."])
                    group["nominees"].remove(nominee_number)
                    break
                elif nominee_number not in teams:
                    errors.append(["error", "("+", ".join(group["team_numbers"])+", etc.) "+
                                 "wanted to be with "+nominee_number+", "+
                                 "but "+nominee_number+" did not want to be with them. " +
                                 " We did not group them together."])
                    group["nominees"].remove(nominee_number)
                    break
                
                nominee = teams[nominee_number]
                if set(nominee["friends"]) & group["team_numbers"]:
                    teams.pop(nominee_number)
                    group["teams"].append(nominee)
                    group["team_numbers"].add(nominee["number"])
                    group["nominees"] |= nominee["friends"]
                    group["nominees"] -= group["team_numbers"]
                    break
            else:
                errors.append(["error", "The group of ("+", ".join(group["team_numbers"])+") "+
                             "wanted to be with ("+", ".join(group["nominees"])+"), "+
                             "but ("+", ".join(group["nominees"])+") did not want to be with them. " +
                             " We did not group them together."])
                break

# Determine shared ranking and date for groups
    for group in groups:
        group["votes"] = defaultdict(lambda: 0)
        for team in group["teams"]:
            group["votes"][team["selections"][0]] += 3
            group["votes"][team["selections"][1]] += 2
            group["votes"][team["selections"][2]] += 1
        tally = group["votes"].items()
        tally.sort(key=lambda t: t[1], reverse=True)
        #This is a HACK for people who selected the same event more than once (assholes)
        if len(tally) < 3:
            tally = tally[:1]*(3-len(tally))+tally
            
        elif len(tally) > 3 or tally[0][1] != 3*tally[2][1] or tally[1][1] != 2*tally[2][1]:
            errors.append(["warning", "The group ("+", ".join(group["team_numbers"])+") did not make all the same event selections. "+
                          "We gave them <br>1: "+tally[0][0]+",<br>2: "+tally[1][0]+",<br>3: "+tally[2][0] ])
            
        group["selections"] = [ tally[0][0], tally[1][0], tally[2][0] ]

    for group in groups:
        group["date"] = max([team["date"] for team in group["teams"]])
        priority_list = [team["priority"] for team in group["teams"]]
        if any(priority_list) and not all(priority_list):
            errors.append(["error", "Some, but not all of ("+", ".join(group["team_numbers"])+") have priority. THE GROUP WILL NOT GET PRIORITY."])
        group["priority"] = all(priority_list)

# Clean up groups
    for group in groups:
        del group["teams"]
        del group["nominees"]
        del group["votes"]

# Filter out priority teams
    one_percent = []
    unwashed_masses = []
    for group in groups:
        if group["priority"]:
            one_percent.append(group)
            events[group["selections"][0]]["open"] -= len(group["team_numbers"])
        else:
            unwashed_masses.append(group)

# Run algorithm
    getSchedule(events, unwashed_masses) # alters "events"

# Put back in important teams
    for group in one_percent:
        event = events[group["selections"][0]]
        event["groups"].append(group)

# Parse back into rows
    results = [["Scheduled Event", "Event Rank", "Group ID"] + src_data[0] ]
    last_group_index = 0
    for event_name, event in events.items():
        for group_index, group in enumerate(event["groups"]):
            for team in group["team_numbers"]:
                team = teamIndex[team]
                row = src_data[team["index"]]
                try:
                    selection_index = team["selections"].index(event_name)+1
                except ValueError:
                    selection_index = 9
                result_row = [event_name, selection_index, last_group_index+group_index+1]+row
                results.append(result_row)
        last_group_index += group_index+1

    return results, errors






