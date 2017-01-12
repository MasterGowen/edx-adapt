#!/usr/bin/env python
"""
Script for manual course setup in edx-adapt application.

Course's required data must be provided in two csv files skills.csv and problems.csv.
IMPORTANT: files must be named as it is mentioned earlier.
Sample of such file is located in edx-adapt/data/BKT dir.

Default values for optional parameters --host, --port, --course, and --course_id_edx are taken from config.py file.
If script is used locally without config.py file nearby, optional parameters become mandatory.
"""

import argparse
import csv
import json
import os
import re
import requests
import sys

try:
    from config import EDX, EDXADAPT
    REQUIRED_PARAMS = False
except ImportError:
    REQUIRED_PARAMS = True

DO_BASELINE_SETUP = False
COURSE_ID = EDX['COURSE_ID']

SKILL2INDEX = {}  # Skill names to their indices
PROBLEM2SKILL = {}  # Dictionary of problems (seq_problemid) to their skill indices
TEST2SKILL = {}  # Dictionary of pretest problems to their skill indices
NUM_PRETEST_PER_SKILL = []  # Number of pretest questions per skill
SKILL2SEQ = []  # list of sets, where the list index is the skill index, and the value is the set of sequentials with
# problems corresponding to that skill
# Variables above are filled using skills.csv file, so any changes to the skill structure must be specified in the
# skills.csv


def get_parameters(required=REQUIRED_PARAMS):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter, description='Setup New Course in Edx Adapt'
    )

    parser.add_argument(
        'csv_files_dir',
        metavar='path/to/csv_files_dir',
        type=str,
        help='path to dir with course setup required csv files: skills.csv and problems.csv.')

    parser.add_argument(
        '--host',
        dest='host',
        type=str,
        default=EDXADAPT['HOST'] if not required else None,
        required=required,
        help='EdxAdapt server hostname or ip-address.'
    )
    parser.add_argument(
        '--host_edx',
        dest='host_edx',
        type=str,
        default=EDX['HOST'] if not required else None,
        required=required,
        help='Open edX LMS hostname.'
    )
    parser.add_argument(
        '--port',
        dest='port',
        type=int,
        default=EDXADAPT['PORT'] if not required else None,
        required=required,
        help='EdxAdapt port.'
    )
    parser.add_argument(
        '--course',
        dest='course_id',
        type=str,
        default=EDXADAPT['COURSE_ID'] if not required else None,
        required=required,
        help='Course which is setup'
    )
    parser.add_argument(
        '--section',
        dest='section',
        type=str,
        default=None,
        help=(
            "Name of section with adaptive problems in Edx course which is added into problem's url. Not need if "
            "coure_id contains section otherwise mandatory"
        )
    )
    parser.add_argument(
        '--https',
        type=bool,
        default=False,
        help="Protocol tutor urls are started with, by default is False (http is used), set True if https is needed."
    )
    params = parser.parse_args()
    return vars(params)


def get_problems_and_skills(path_to_dir):
    """
    Parse csv files with problems and skills description data and prepare a list.
    """
    if not os.path.exists(path_to_dir):
        print("Dir with csv files: {} does not exist, please try again".format(path_to_dir))
        sys.exit()
    files = ('skills', 'problems')
    csv_path_files = {}
    for i in range(2):
        path_to_file = os.path.join(path_to_dir, files[i] + '.csv')
        if os.path.isfile(path_to_file):
            csv_path_files[files[i]] = path_to_file
    print(csv_path_files)
    return csv_path_files


def setup_course_in_edxadapt(**kwargs):
    """
    Add course into edx-adapt.

    Skills are taken from skills.csv and course's problems from problems.csv
    """
    csv_path_files = get_problems_and_skills(kwargs['csv_files_dir'])
    headers = {'Content-type': 'application/json'}
    payload = json.dumps({'course_id': kwargs['course_id']})
    requests.post('http://{host}:{port}/api/v1/course'.format(**kwargs), data=payload, headers=headers)
    with open(csv_path_files['skills'], "r") as fin:
        max_skill_index = 0
        pretest2skill = {}
        lines = csv.reader(fin)
        for tokens in lines:
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
        requests.post('http://{host}:{port}/api/v1/course/{course_id}/skill'.format(**kwargs), data=payload, headers=headers)

    payload = json.dumps({'skill_name': "None"})
    requests.post('http://{host}:{port}/api/v1/course/{course_id}/skill'.format(**kwargs), data=payload, headers=headers)
    table = [line.strip().split(',') for line in open(csv_path_files['problems']).readlines()]
    for row in table:
        msg = (
            "Course_id doesn't contain section where adaptive problem are placed in the course, and optional "
            "parameter 'section' is empty. Improve 'course_id' or fulfill 'section' parameter and run again."
        )
        pname = row[0]
        skill = row[1]
        # NOTE(idegtiarov) with two or more sections in the course with adaptive problems course_id should contain
        # section otherwise 'section' should be added as optional parameter to be added in the url
        course_id_list = kwargs['course_id'].split(':')
        part_url = 'course-v1:'
        if len(course_id_list) == 1:
            if not kwargs['section']:
                print(msg)
                sys.exit()
            else:
                part_url += course_id_list[0] + '/courseware/' + kwargs['section']
        else:
            # part_url += course_id_list[0] + '/courseware/' + course_id_list[1]
            part_url += course_id_list[0] + '/jump_to_id'

        url = '{protocol}://{host_edx}/courses/{part_url}/{pname}'.format(
            protocol=('https' if kwargs['https'] else 'http'), pname=pname, part_url=part_url, **kwargs
        )

        pre = "Pre_a" in pname
        post = "Post_a" in pname
        payload = json.dumps({
            'problem_name': pname, 'tutor_url': url, 'skills': [skill], 'pretest': pre, 'posttest': post
        })
        requests.post('http://{host}:{port}/api/v1/course/{course_id}'.format(**kwargs), data=payload, headers=headers)

    payload = json.dumps({'experiment_name': 'test_experiment2', 'start_time': 1462736963, 'end_time': 1999999999})
    requests.post('http://{host}:{port}/api/v1/course/{course_id}/experiment'.format(**kwargs), data=payload, headers=headers)

    if DO_BASELINE_SETUP:
        params = {'pi': 0.1, 'pt': 0.1, 'pg': 0.1, 'ps': 0.1, 'threshold': 1.0}
        tutor_params = {}
        for skill in ['d to h', 'y axis', 'h to d', 'center', 'shape', 'x axis', 'histogram', 'spread']:
            tutor_params[skill] = params
        requests.post(
            'http://{host}:{port}/api/v1/misc/SetBOParams'.format(**kwargs),
            data=json.dumps({'course_id': kwargs['course_id'], 'parameters': tutor_params}),
            headers=headers
        )


if __name__ == '__main__':
    parameters = get_parameters()
    print(parameters)
    setup_course_in_edxadapt(**parameters)
