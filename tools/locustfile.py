from random import choice, randint

from locust import HttpLocust, TaskSet

import resource
print(resource.getrlimit(resource.RLIMIT_NOFILE))
# resource.setrlimit(resource.RLIMIT_NOFILE, (999999, 999999))
# print(resource.getrlimit(resource.RLIMIT_NOFILE))

# TIMETOUTS = (100, 100)  # Connect & read timetouts

STUDENT_NAMES = ['load_user_{}'.format(i) for i in range(1, 5000)]
PROBLEMS = [
    'axis_0', 'axis_1', 'b3', 'b3_2_0', 'b3_2_1', 'b3data_0', 'b3data_1',
    'b3labels', 'b4', 'b4_2_0', 'b4_2_1', 'b5_center', 'b5_shape', 'b5_spread',
    'labeling_a', 'match_d_to_h', 'match_h_to_d_0', 'match_h_to_d_1',
    'match_h_to_d_a', 'matching_a', 'matching_b', 'matching_desc_hist_a',
    'p3_0', 'p3_1', 'Post_assessment_0', 'Post_assessment_1', 'Post_assessment_10',
    'Post_assessment_11', 'Post_assessment_12', 'Post_assessment_13',
    'Post_assessment_2', 'Post_assessment_3', 'Post_assessment_4',
    'Post_assessment_5', 'Post_assessment_6', 'Post_assessment_7',
    'Post_assessment_8', 'Post_assessment_9', 'practice_label_x',
    'practice_label_y', 'practice_label2_x', 'practice_label2_y',
    'practice_label3_x', 'practice_label3_y', 'practice_label_des',
    'practice_label2_des', 'practice_label3_des', 'Pre_assessment_0',
    'Pre_assessment_1', 'Pre_assessment_10', 'Pre_assessment_11',
    'Pre_assessment_12', 'Pre_assessment_13', 'Pre_assessment_2',
    'Pre_assessment_3', 'Pre_assessment_4', 'Pre_assessment_5',
    'Pre_assessment_6', 'Pre_assessment_7', 'Pre_assessment_8',
    'Pre_assessment_9', 'shape_0', 'shape_1', 'skew_easy_0', 'skew_easy_1',
    'skew_easy_2', 'skew_easy_3', 'skew_easy_4', 'skew_easy_5', 'skew_easy_6',
    'skew_easy2_1', 'skew_easy2_2', 'skew_easy2_3', 'skew_easy2_4', 'skew_easy2_5',
    'skew_easy2_6', 'T3', 'T3_2', 't4_2_0', 't4_2_1', 't5_center', 't5_shape',
    't5_spread', 'labels_we'
]


def login(l):
    l.client.post("/login", {"username": "ellen_key", "password": "education"})
        # timeout=TIMETOUTS


def data_export(l):
    l.client.get('/api/v1/misc/dataexport')
        # timeout=TIMETOUTS


def course(l):
    l.client.get('/api/v1/course/CMUSTAT101')
        # timeout=TIMETOUTS


def student(l):
    student_name = choice(STUDENT_NAMES)
    l.client.get('/api/v1/course/CMUSTAT101/user/{}'.format(student_name),
                 name='/api/v1/course/CMUSTAT101/user/[name]')
        # timeout=TIMETOUTS


def answer_problem(l):
    problem = choice(PROBLEMS)
    student_name = choice(STUDENT_NAMES)
    payload = {
        'problem': problem,
        'correct': 0,
        'attempt': 1
    }

    l.client.options('/api/v1/course/CMUSTAT101/user/{}/interaction'.format(student_name),
                     json=payload,
                     name='/api/v1/course/CMUSTAT101/user/[name]/interaction')
        # timeout=TIMETOUTS
    l.client.post('/api/v1/course/CMUSTAT101/user/{}/interaction'.format(student_name),
                  json=payload,
                  name='/api/v1/course/CMUSTAT101/user/[name]/interaction')
        # timeout=TIMETOUTS


def log_pageload(l):
    student_name = 'load_user_{}'.format(randint(1, 10))
    problem = choice(PROBLEMS)
    data = {'problem': problem}
    l.client.options('/api/v1/course/CMUSTAT101/user/{}/pageload'.format(student_name),
                     name='/api/v1/course/CMUSTAT101/user/[name]/pageload')
        # timeout=TIMETOUTS
    l.client.post('/api/v1/course/CMUSTAT101/user/{}/pageload'.format(student_name),
                  json=data,
                  name='/api/v1/course/CMUSTAT101/user/[name]/pageload')
        # timeout=TIMETOUTS


class UserBehavior(TaskSet):
    tasks = {
        # course: 10,
        student: 233,
        answer_problem: 100,
        # pageload_options: 19,
        # pageload_post: 30,
        log_pageload: 30,
        # interaction_options: 14,
        # interaction_post: 28,
        # data_export: 1
        }

    # def on_start(self):
    #     login(self)


class WebsiteUser(HttpLocust):
    task_set = UserBehavior
    min_wait = 5000
    max_wait = 60000
