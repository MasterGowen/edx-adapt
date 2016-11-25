import json
import re

from config import EDX, EDXADAPT
from edx_adapt.api import adapt_api

DO_BASELINE_SETUP = False
COURSE_ID = EDX['COURSE_ID']

SKILL2INDEX = {}  # Skill names to their indices
PROBLEM2SKILL = {}  # Dictionary of problems (seq_problemid) to their skill indices
TEST2SKILL = {}  # Dictionary of pretest problems to their skill indices
NUM_PRETEST_PER_SKILL = []  # Number of pretest questions per skill
SKILL2SEQ = []  # list of sets, where the list index is the skill index, and the value is the set of sequentials with
# problems corresponding to that skill
# The above are filled using skills.csv file, so any changes to the skill structure must be specified in the skills.csv


def setup_course_in_edxadapt(course_id):
    """
    Add course into edx-adapt.
    
    Skills are taken from skill_test.csv and course's problems from problist.tsv
    """
    app = adapt_api.app.test_client()
    headers = {'Content-type': 'application/json'}
    payload = json.dumps({'course_id': course_id})
    app.post('/api/v1/course', data=payload, headers=headers)
    with open("data/BKT/skills_test.csv", "r") as fin:
        max_skill_index = 0
        pretest2skill = {}
        for line in fin:
            tokens = line.strip().split(",")
            if tokens[2] not in SKILL2INDEX:
                SKILL2INDEX[tokens[2]] = max_skill_index
                max_skill_index += 1
                SKILL2SEQ.append(set())
                NUM_PRETEST_PER_SKILL.append(0)
            skill_index = SKILL2INDEX[tokens[2]]

            if re.match('^Pre.*assessment$', tokens[0]):
                pretest2skill[int(tokens[1])] = skill_index
                NUM_PRETEST_PER_SKILL[skill_index] += 1
            else:
                PROBLEM2SKILL[tokens[0]+"_"+tokens[1]] = skill_index
                SKILL2SEQ[skill_index].add(tokens[0])

        for key in pretest2skill:
            TEST2SKILL[key] = pretest2skill[key]

    for k in SKILL2INDEX:
        payload = json.dumps({'skill_name': k})
        app.post('/api/v1/course/{}/skill'.format(course_id), data=payload, headers=headers)

    payload = json.dumps({'skill_name': "None"})
    app.post('/api/v1/course/{}/skill'.format(course_id), data=payload, headers=headers)
    table = [line.strip().split('\t') for line in open("data/BKT/problist.tsv").readlines()]
    for row in table:
        pname = row[0]
        skill = row[1]
        url = 'http://{HOST}/courses/{COURSE_ID}/courseware/statistics/{pname}'.format(pname=pname, **EDX)

        pre = "Pre_a" in pname
        post = "Post_a" in pname
        payload = json.dumps({
            'problem_name': pname, 'tutor_url': url, 'skills': [skill], 'pretest': pre, 'posttest': post
        })
        app.post('/api/v1/course/{}'.format(course_id), data=payload, headers=headers)

    payload = json.dumps({'experiment_name': 'test_experiment2', 'start_time': 1462736963, 'end_time': 1999999999})
    app.post('/api/v1/course/{}/experiment'.format(course_id), data=payload, headers=headers)

    if DO_BASELINE_SETUP:
        params = {'pi': 0.1, 'pt': 0.1, 'pg': 0.1, 'ps': 0.1, 'threshold': 1.0}
        tutor_params = {}
        for skill in ['d to h', 'y axis', 'h to d', 'center', 'shape', 'x axis', 'histogram', 'spread']:
            tutor_params[skill] = params
        app.post(
            '/api/v1/misc/SetBOParams'.format(**EDXADAPT),
            data=json.dumps({'course_id': course_id, 'parameters': tutor_params}),
            headers=headers
        )

if __name__ == '__main__':
    setup_course_in_edxadapt(COURSE_ID)
