import requests, json, sys
from config import EDX, EDXADAPT
DO_BASELINE_SETUP = False
COURSE_ID = 'course-v1:CMU+STAT101+2014_T1'
EDXADAPT_HOST = sys.argv[1]
EDX_HOST = sys.argv[2]

headers = {'Content-type': 'application/json'}
payload = json.dumps({'course_id':'CMUSTAT101'})
r = requests.post('http://{HOST}:{PORT}/api/v1/course'.format(**EDXADAPT), data=payload, headers=headers)
print str(r) + str(r.json())

skill2index = {} # Skill names to their indices
problem2skill = {} # Dictionary of problems (seq_problemid) to their skill indices
test2skill = {} # Dictionary of pretest problems to their skill indices
num_pretest_per_skill = [] # Number of pretest questions per skill
skill2seq = [] # list of sets, where the list index is the skill index, and the value is the set of sequentials with problems corresponding to that skill
# The above are filled using skills.csv file, so any changes to the skill structure must be specified in the skills.csv

with open("../data/BKT/skills_test.csv", "r") as fin:
    max_skill_index = 0
    pretest2skill = {}
    for line in fin:
        tokens = line.strip().split(",")
        if tokens[2] not in skill2index:
            skill2index[tokens[2]] = max_skill_index
            max_skill_index += 1
            skill2seq.append(set())
            num_pretest_per_skill.append(0)
        skill_index = skill2index[tokens[2]]

        if tokens[0].endswith("assessment"):
            if tokens[0].startswith("Pre"):
                pretest2skill[int(tokens[1])] = skill_index
                num_pretest_per_skill[skill_index] += 1
        else:
            problem2skill[tokens[0]+"_"+tokens[1]] = skill_index
            skill2seq[skill_index].add(tokens[0])

    test2skill = [0] * len(pretest2skill)
    for key in pretest2skill:
        test2skill[key] = pretest2skill[key]

print pretest2skill
print skill2seq
print skill2index

for k,v in skill2index.iteritems():
    payload = json.dumps({'skill_name':k})
    r = requests.post('http://{HOST}:{PORT}/api/v1/course/{COURSE_ID}/skill'.format(**EDXADAPT), data=payload, headers=headers)
    print str(r) + str(r.json())

payload = json.dumps({'skill_name':"None"})
r = requests.post('http://{HOST}:{PORT}/api/v1/course/{COURSE_ID}/skill'.format(**EDXADAPT), data=payload, headers=headers)
print str(r) + str(r.json())

"""
f = open('../course-content/old_new_map.json', 'r')
old_new = json.loads(f.readline())

with open("../data/BKT/skills_test.csv", "r") as fin:
    for line in fin:
        tokens = line.strip().split(",")
        prob = tokens[0] + "_" + tokens[1]

        skill = tokens[2]

        print prob

        if prob in old_new:
            prob = old_new[prob]
            if prob == "axis":
                payload = {'problem_name':'axis_0', 'tutor_url':'http://cmustats.tk/courses/CMU/STAT101/2014_T1/courseware/statistics/axis_0',
                'skills':['y_axis']}
            else:
                payload = {'problem_name':prob, 'tutor_url':'http://cmustats.tk/courses/CMU/STAT101/2014_T1/courseware/statistics/'+prob,
                'skills':[skill]}
            print "\t\told_new"

        else:
            if tokens[0] == "axis":
                payload = {'problem_name':'axis_0', 'tutor_url':'http://cmustats.tk/courses/CMU/STAT101/2014_T1/courseware/statistics/axis_0',
                'skills':['y_axis']}
            else:
                payload = {'problem_name':tokens[0], 'tutor_url':'http://cmustats.tk/courses/CMU/STAT101/2014_T1/courseware/statistics/'+tokens[0],
                'skills':[skill]}
            print "\t\tregular"

        print "\t\t" + str(tokens)

        if "Pre_as" in prob:
            payload['pretest'] = True
        if "Post_as" in prob:
            payload['posttest'] = True

        if payload['problem_name'] == "T3_2" and 'histogram' in payload['skills']:
            continue

        r = requests.post('http://'+EDXADAPT_HOST+':8080/api/v1/course/CMUSTAT101', data=json.dumps(payload), headers=headers)
        print str(r) + str(r.json())
"""

table = [line.strip().split('\t') for line in open("problist.tsv").readlines()]

for row in table:
    pname = row[0]
    skill = row[1]
    url = 'http://{HOST}/courses/{COURSE_ID}/courseware/statistics/{pname}'.format(pname=pname, **EDX)
    pre = False
    post = False

    if "Pre_a" in pname:
        pre = True
    if "Post_a" in pname:
        post = True

    payload = {'problem_name': pname, 'tutor_url': url, 'skills': [skill], 'pretest': pre, 'posttest': post}
    r = requests.post('http://{HOST}:{PORT}/api/v1/course/{COURSE_ID}'.format(**EDXADAPT), data=json.dumps(payload), headers=headers)
    print str(r) + str(r.json())


payload = json.dumps({'experiment_name':'test_experiment2', 'start_time':1462736963, 'end_time':1999999999})
r = requests.post('http://{HOST}:{PORT}/api/v1/course/{COURSE_ID}/experiment'.format(**EDXADAPT), data=payload, headers=headers)
print str(r) + str(r.json())


if DO_BASELINE_SETUP:
    params = {'pi': 0.1, 'pt': 0.1, 'pg': 0.1, 'ps': 0.1, 'threshold': 1.0 }
    tutor_params = {}
    for skill in ['d to h', 'y axis', 'h to d', 'center', 'shape', 'x axis', 'histogram', 'spread']:
        tutor_params[skill] = params
    #ping back the server with the new parameters
    response = requests.post('http://{HOST}:{PORT}/api/v1/misc/SetBOParams'.format(**EDXADAPT),
                             data=json.dumps({'course_id':EDXADAPT['COURSE_ID'], 'parameters': tutor_params}), headers=headers)

