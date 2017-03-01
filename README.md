# Adaptive problem selection interface for EdX courses

[![Travis](https://img.shields.io/travis/raccoongang/edx-adapt.svg)](https://travis-ci.org/raccoongang/edx-adapt)
[![Code Climate](https://img.shields.io/codeclimate/github/raccoongang/edx-adapt.svg)](https://codeclimate.com/github/raccoongang/edx-adapt)

## Installation

Edx-Adapt application requires
[MongoDB](https://docs.mongodb.com/manual/administration/install-on-linux/)
database.

Clone edx-adapt project to your server and switch to the project
directory:

```bash
> git clone git@github.com:raccoongang/edx-adapt.git@<tag_stable_version>
> cd edx-adapt
```

Create virtual environment:

```bash
> virtualenv env_name
```

Activate virtual environment and install all requirements:

```bash
> source env_name/bin/activate
> pip install -r requirements
```

## Run edx-adapt application in development mode

```
> python edx_adapt.py
```

## Run edx-adapt application in production mode

There are few sample config files in `etc/folder` required to configure
production environment.

`etc/nginx/` contains template file to configure nginx server

`etc/edx_adapt/` contains template file to configure uwsgi server for
edx-adapt

`etc/init/` contains template file to configure edx-adapt be proceed by
service manager

## Main API endpoints

`/api/v1/course`

- GET: Show all courses registered in Edx-Adapt
  - `response.data = {'course_ids': courses}`
- POST: Create new course in Edx-Adapt
  - Parameters: `course_id` (string)

`/api/v1/course/<course_id>/skill`

- GET: Show all skills which course `<course_id>` contains.
  - `response.data = {'skills': skills}`
- POST: Add skill into course `<course_id>`
  - Parameters : `skill_name` (string)

`/api/v1/course/<course_id>/user`

- GET: Show all users registered in the course `<course_id>`
  - `response.data = {'users': {'finished': finished_users,
  'in_progress': progress_users}}`
- POST: Enroll new user in the course `<course_id>`
  - Parameters: `user_id` (string)

`/api/v1/course/<course_id>`

- GET: Show all problems contained to the course `<course_id>`
  - `response.data = {'problems': problems}`
- POST: Add new problem in the course `<course_id>`
  - Parameters: `problem_name` (string), `tutor_url` (string), `skills`
    (list of strings), `pretest` (boolean), `posttest` (boolean)

`/api/v1/course/<course_id>/skill/<skill_name>`

- GET: Show all problems contained in the course `<course_id>` related
  to the skill `<skill_name>`
  - `response.data = {'problems': problems}`

`/api/v1/course/<course_id>/experiment`

- GET: Show result of all experiments for the course `<course_id>`
  - `response.data = {'experiments': exps}`

`/api/v1/course/<course_id>/probabilities`

- GET: Show list with default BKT model parameters added to the course
  `<course_id>`
  - `response.data = {'model_params': prob_list}`

- POST: Add new or update existing model parameters in the course
  `<course_id>`
  - Parameters: `prob_list` (list of dicts with models parameters)
    `[{threshold: float, pg: float, ps: float, pi: float, pt: float},
    ...]`

`/api/v1/course/<course_id>/user/<user_id>/interaction`

- POST: Add user's interaction with Edx into Edx-Adapt
  - Parameters: `problem` (string), `correct` (int), `attempt` (int),
    `unix_seconds` (string)

`/api/v1/course/<course_id>/user/<user_id>`

- GET: Show user's status:
  - `reponse.data = {
    "next": next_problem, "current": current_problem,
    "done_with_current": done_with_current, "okay": okay,
    "done_with_course": done_with_course
  }`

`/api/v1/course/<course_id>/user/<user_id>/pageload`

- POST: Add logging information about problem visited by user into
  Edx-Adapt
  - Parameters: `problem` (string), `unix_seconds` (string)

`/api/v1/parameters/bulk`

- POST: Add BKT model parameters to each course's skill for the user
  - Parameters: `course_id` (string), `user_id` (string), `skills_list`
    (list of strings)

`/api/v1/data/logs/course/<course_id>/user/<user_id>/problem/<problem_name>`

- GET: Show collected log data for users `<user_id>` interaction with
  problem `<problem_name>` on the course `<course_id>`
  - `response.data = {'log': problem log}`

`/api/v1/data/logs/course/<course_id>/user/<user_id>`

- GET: Show all collected log data for user `<user_id>` interaction on
  the course `<course_id>`
  - `response.data = {'log': log data}`

`/api/v1/data/logs/course/<course_id>`

- GET: Show all collected data for every user with status "in progress"
  on the course `<course_id>`
  - `response.data = {'log': log data}`

`/api/v1/data/logs/course/<course_id>/experiment/<experiment_name>`

- GET: Show all collected log data for users successfully passed
  experiment `<experiment_name>` on the course `<course_id>`
  - `response.data = {'log': log data}`

`/api/v1/data/trajectory/course/<course_id>/user/<user_id>`

- GET: Show trajectory of the user `<user_id>` interaction with the
  course `<course_id>`
  - `response.data = {'data': {}, 'trajectories': {}, 'pretest_length':
 {}, 'posttest_length': {}}`

`/api/v1/data/trajectory/course/<course_id>`

- GET: Show trajectory for all users with status "in progress" in the
  course `<course_id>`
  - `response.data = {<user_id_1>: {'data': {}, 'trajectories': {},
    'pretest_length': {}, 'posttest_length': {}}, <user_id_2>: {}, ...}`

## Data models stored in the database

Data stored in MongoDB as documents, which are represented as JSON
objects.

Edx-adapt uses one database and 4 collections for each Course. Two
collections are generic for all courses and two collections are created
specifically for certain course.

### Generic collections are: `Courses` and `Generic`

#### `Courses` collection stores documents with base information about the course

```js
{
    _id: ObjectID(),  // document's unique id, generated by MongoDB itself
    users_finished: [],  // list of users who have finished course
    skills: [],  // list of course's skills
    problems: [  // list of course's problems
        {  // dict describes the problem
            skills: [],  // list of skills related to the problem
            pretest: false,  // boolean flag to show if problem is pretest
            posttest: false,  // boolean flag to show if problem is posttest
            tutor_url: <problem_url>,  // problem's url. E.g. on the Open edX course
        },
        ...
    ],
    users_in_progress: [],  // list of "in progress" users
    experiments: [  // list of experiments definitions
        {
            experiment_name: <string>,
            start_time: <Int32>,
            end_time: <Int32>
        },
        ...
    ],
    course_id: <string>,  // unique course id
    model_params: [  // list with model's parameters
        {
            threshold: <double>,  // <double> is bson float type
            pg: <double>,
            ps: <double>,
            pi: <double>,
            pt: <double>,
        },
        ...
    ],
}
```

#### `Generic` collection stores all student - skills related data

```js
{
    _id: ObjectID(),
    key: <string>,  // unique compound key, which contains <course_id>,
                    // <user_id>, and <skill_name>
    val: {
          threshold: <double>,
          pg: <double>,
          ps: <double>,
          pi: <double>,
          pt: <double>,
    }
}
```

### Course specific collections

#### `<course_id>_log` collects all logs about students' interactions

Adaptive logging includes page load data and student's responses on
problems questions.

##### Interaction log doc

```js
{
     _id: ObjectID(),
     unix_s: <Int32>,
     attempt: <Int32>,
     student_id: <string>,
     timestamp: <string>,
     problem: {
         skills: [],
         pretest: false,
         posttest: false,
         tutor_url: <problem_url>,
    },
    type: "response",
    correct: 0  // possible values 1 and 0 for correct and incorrect answers correspondingly
}
```

##### Page load log doc

```js
{
     _id: ObjectID(),
     unix_s: <Int32>,
     student_id: <string>,
     timestamp: <string>,
     problem: {
         skills: [],
         pretest: false,
         posttest: false,
         tutor_url: <problem_url>,
    },
    type: "page_load"
}
```

#### `<course_id>_problems` is a collection with the student's current status

Status includes problems which were selected by Edx-Adapt for the
student on every step through the adaptive course

```js
{
     _id: ObjectID(),
     current: {  // could be problem described dict or null object
          problem: {
          skills: [],
          pretest: false,
          posttest: false,
          tutor_url: <problem_url>,
     },
     next: null,  // Possible values: dict with problem description, null.
     student_id: <string>,
     perm: false,  // (experimental attribute) boolean flag shows if student
                   // has permissions for fluent navigation.
                   // Permission is changed after student start to answer on
                   // post-assessment problems
     nav: "adapt"  // Save initial student permission. Possible value "adapt"
                   // and "free", "adapt" is default behavior
                   // (perm == false), "free" (perm == true) student had
                   // permissions for free navigation throug adaptive problems
}
```
