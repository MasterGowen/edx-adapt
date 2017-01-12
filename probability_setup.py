#!/usr/bin/env python
"""
Script to manually enroll students in edx-adapt application.

Student's anonymous ids are downloaded from Edx lms Course/Instructor/Data Download/ page as csv file.
Sample of such file is located in edx-adapt/data dir.

Default values for optional parameters --host, --port, --course are taken from config.py file. If script is used
locally without config.py file nearby, optional parameters: --host, --port, --course become mandatory.
Additionally optional parameters --prob and --skills can be set, if default values are not suitable.
"""
import argparse
import json

import requests

try:
    from config import EDXADAPT, EDX
    REQUIRED_PARAMS = False
except ImportError:
    REQUIRED_PARAMS = True


def get_parameters(required=REQUIRED_PARAMS):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter, description='Enroll students from csv file.'
    )

    parser.add_argument(
        dest='prob_list',
        type=json.loads,
        nargs='+',
        help=(
            'dict with BKT model probabilities student will be enrolled with, example is '
            '\'{"pg": 0.25, "ps": 0.25, "pi": 0.1, "pt": 0.5, "threshold": 0.99}\''
        )
    )
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
        default=EDX['COURSE_ID'] if not required else None,
        required=required,
        help='course student is enrolled in.'
    )
    parser.add_argument(
        '--update',
        dest='update_probs',
        type=bool,
        default=False,
        help='boolean flag to mark that update is required instead of replacement.'
    )
    params = parser.parse_args()
    return vars(params)


def store_model_params():
    parameters = get_parameters()
    headers = {'Content-type': 'application/json'}
    payload = {'course_id': parameters['course_id'], 'prob_list': parameters['prob_list']}

    if parameters['update_probs']:
        req = requests.put(
            'http://{host}:{port}/api/v1/course/{course_id}/probabilities'.format(**parameters),
            json=payload,
            headers=headers
        )
    else:
        req = requests.post(
            'http://{host}:{port}/api/v1/course/{course_id}/probabilities'.format(**parameters),
            json=payload,
            headers=headers
        )
    if req.status_code == 201:
        print("Probability parameters: {}, are added into Course - {}".format(
            parameters['prob_list'], parameters['course_id']
        ))
    else:
        print("Probability parameters were not added, status: {}, reason: {}".format(req.status_code, req.reason))


def main():
    store_model_params()


if __name__ == '__main__':
    main()
