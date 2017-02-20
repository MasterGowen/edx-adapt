#!/usr/bin/env python
"""
Script for manual enroll students in edx-adapt application.

Student's anonymous ids are downloaded from Edx lms Course/Instructor/Data Download/ page as csv file.
Sample of such file is located in edx-adapt/data dir.

Default values for optional parameters --host, --port, --course are taken from config.py file. If script is used
locally without config.py file nearby, optional parameters: --host, --port, --course become mandatory.
Additionally could be set optional parameters --prob and --skills if default values are not appropriate.
"""
import argparse
import csv
import json
import os
import sys

import requests

try:
    from config import EDXADAPT
    REQUIRED_PARAMS = False
except ImportError:
    REQUIRED_PARAMS = True

DEFAULT_PROBABILITIES = {'pg': 0.25, 'ps': 0.25, 'pi': 0.1, 'pt': 0.5, 'threshold': 0.99}


def get_parameters(required=REQUIRED_PARAMS):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter, description='Enroll students from csv file.'
    )

    parser.add_argument('csvfile', metavar='file.csv', type=str, help='path/to/csv/file with anonymous student ids.')

    parser.add_argument(
        '--host',
        dest='host',
        type=str,
        default=EDXADAPT['HOST'] if not required else None,
        required=required,
        help='host of the edx-adapt server.'
    )
    parser.add_argument(
        '--port',
        dest='port',
        type=int,
        default=EDXADAPT['PORT'] if not required else None,
        required=required,
        help='port of the edx-adapt server.'
    )
    parser.add_argument(
        '--course',
        dest='course_id',
        type=str,
        default=EDXADAPT['COURSE_ID'] if not required else None,
        required=required,
        help='Course ID of the course student is enrolling in.'
    )
    parser.add_argument(
        '--prob',
        dest='probabilities',
        type=json.loads,
        default=DEFAULT_PROBABILITIES,
        help=(
            'dict with BKT model probabilities student will be enrolled with, default is '
            '\'{"pg": 0.25, "ps": 0.25, "pi": 0.1, "pt": 0.5, "threshold": 0.99}\''
        )
    )
    parser.add_argument(
        '-v',
        '--verbose',
        help='increase output verbosity'
    )
    params = parser.parse_args()
    return vars(params)


def get_students_for_enrollment(headers, **kwargs):
    """
    Parse csv file with student anonymous data and prepare a list of students for enrollment in edx-adapt.
    """
    path_to_file = kwargs['csvfile']
    if not os.path.exists(path_to_file):
        print("File with path: {} does not exist, please try again".format(path_to_file))
        sys.exit()
    enrolled_students = get_enrolled_students(headers, **kwargs)
    with open(path_to_file) as csvfile:
        raw_students_ids = csv.DictReader(csvfile)
        for line in raw_students_ids:
            user_id = line['Anonymized User ID']
            key = (
                'started' * (user_id in enrolled_students['started']) +
                'updated' * (user_id in enrolled_students['not_started'])
            )
            yield user_id, key if key else 'enrolled'


def check_users_already_started(users_list, headers=None, **kwargs):
    """
    Check whether user have already started course if not users parameters could be updated
    :param users_list: list with users_in_progress
    :return: checked_users: dict with {'started': [...], 'not_started': [...]}  lists of users
    """
    checked_users = {'started': [], 'not_started': []}
    for user in users_list:
        status = requests.get(
            'https://{host}:{port}/api/v1/course/{course_id}/user/{user_id}'.format(user_id=user, **kwargs),
            headers=headers
        ).json()
        if status['current']:
            checked_users['started'].append(user)
        else:
            checked_users['not_started'].append(user)
    return checked_users


def get_enrolled_students(headers, **kwargs):
    """
    Get student already enrolled in edx-adapt.
    """
    users = requests.get('https://{host}:{port}/api/v1/course/{course_id}/user'.format(**kwargs), headers=headers)
    if users:
        users = users.json()
        enrolled_users = {'started': set(), 'not_started': set()}
        enrolled_users['started'].update(set(users['users']['finished']))
        checked_users = check_users_already_started(users['users']['in_progress'], headers, **kwargs)
        enrolled_users['started'].update(set(checked_users['started']))
        enrolled_users['not_started'].update(set(checked_users['not_started']))
        return enrolled_users
    else:
        print("Course or edx-adapt server is not found")
        sys.exit()


def output_result(student_to_adapt, verbose=False):
    if verbose:
        for key in student_to_adapt:
            student_to_adapt[key] = " ,\n".join(student_to_adapt[key])
    print("Enrolled: {enrolled}; Updated: {updated}; Ignored: {started}".format(**student_to_adapt))


def main():
    parameters = get_parameters()
    headers = {'Content-type': 'application/json'}
    student_id_list = get_students_for_enrollment(headers, **parameters)
    student_to_adapt = {'enrolled': [], 'updated': [], 'started': []}
    for student_id, key in student_id_list:
        student_to_adapt[key].append(student_id)
        if key == 'started':
            continue
        else:
            payload = {
                'course_id': parameters['course_id'],
                'params': parameters['probabilities'],
                'user_id': student_id,
            }
            req = requests.post(
                'https://{host}:{port}/api/v1/parameters/bulk'.format(**parameters), json=payload, headers=headers
            )
            if req.status_code == 200:
                print("student's skills are added")
            else:
                print(
                    "Cannot create skills documemts for the student {}. Student cannot be enrolled without existed "
                    "course skills. Please repeat enrollment procedure for this student ones more time.".format(
                        student_id
                    )
                )
                continue

            payload = {'user_id': student_id}
            req = requests.post(
                'https://{host}:{port}/api/v1/course/{course_id}/user'.format(**parameters),
                json=payload,
                headers=headers
            )
            if req.status_code == 200:
                print("Student {} is enrolled on the course {}".format(student_id, parameters['course_id']))
            else:
                print(
                    "Failed to enroll student {} to the course {}. Please repeat enrollment procedure for this student "
                    "ones more time.".format(student_id, parameters['course_id'])
                )
                continue
    output_result(student_to_adapt, verbose=parameters['verbose'])


if __name__ == '__main__':
    main()
