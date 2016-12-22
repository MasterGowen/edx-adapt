import os
import sys

name = sys.argv[1]

os.system('python user_setup_test.py ' + name)
for c in range(100):
    os.system('python question_test.py ' + name + ' 0')
