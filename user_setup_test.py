import json, sys, requests

from config import EDX, EDXADAPT

user = sys.argv[1]
headers = {'Content-type': 'application/json'}

payload = json.dumps({'user_id':user})
r = requests.post('http://{HOST}:{PORT}/api/v1/course/{COURSE_ID}/user'.format(**EDXADAPT), data=payload, headers=headers)
print str(r) + str(r.json())

# give some problems
p = {'pg': 0.25, 'ps': 0.25, 'pi': 0.1, 'pt': 0.5, 'threshold':0.99}
# p = {'pg': 0.01, 'ps': 0.01, 'pi': 0.99, 'pt': 0.99, 'threshold':0.90}
# p = {'pg': 0.5, 'ps': 0.5, 'pi': 0.01, 'pt': 0.01, 'threshold':0.95}
skills = ['center', 'shape', 'spread', 'x axis', 'y axis', 'h to d', 'd to h', 'histogram', 'None']

for skill in skills:
    payload = json.dumps({'course_id':EDXADAPT['COURSE_ID'], 'params': p, 'user_id':user, 'skill_name':skill})
    r = requests.post('http://{HOST}:{PORT}/api/v1/parameters'.format(**EDXADAPT), data=payload, headers=headers)
    print str(r) + str(r.json())

