#!/usr/bin/env python
import argparse
import os
import re
import sys
from xml.dom import minidom
import xml.etree.ElementTree as ET


CHOICE_ELEMENTS = ('multiplechoiceresponse', 'choiceresponse')
FEEDBACK_KEYS = {'multiplechoiceresponse': "answer['inputs'].index(1)]", 'choiceresponse': "tuple(answer['inputs'])"}


def get_parameters():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter, description='Transform xml problem into capa from the file.'
    )

    parser.add_argument(
        'xmlsource', metavar='dir|file.xml', type=str, help='path/to/dir/with/problems or path/to/problem/file.'
    )

    parser.add_argument('output_dir', type=str, help='path/to/dir/with/adaptive/problems with new created problem.')

    parser.add_argument(
        '--regex',
        type=str,
        help='python regex expression which is used to choose problems from source to transform.'
    )
    return parser.parse_args()


def pretty_print(element):
    """
    Get ElementTree element and returns element structure in a 'pretty' xml view.
    """
    rough_string = ET.tostring(element, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def parse_text_field(element, indent=0, prefix='', postfix='', tagwrap=True, restrict_elem=None):
    """
    Parse ElementTree elements structure and returns string with escaping tags brackets

    :param element: ElementTree element
    :param indent: additional indentation which is added to each new string
    :param prefix: prefix string which is added to each new string
    :param postfix: postfix string which is added to each new string
    :param tagwrap: boolean flag to add or not initial element's tag into resulting string
    :param restrict_elem: name of the element which is not added into resulting string
    :return: string with element's structure
    """
    tag = element.tag
    attrib = ""
    if element.attrib:
        for attr, value in element.attrib.iteritems():
            attrib += " {}='{}'".format(attr, value)
    text_param = (' '.join(element.text.split()) if element.text else '')
    text = ('{0:>{indent}}{prefix}' + ('&lt;{tag}{attrib}&gt;' if tagwrap else '') + '{text}').format(
        "", indent=indent, prefix=prefix, tag=tag, attrib=attrib, text=text_param
    )
    if len(element) > 0:
        for subelement in element:
            if subelement.tag == restrict_elem:
                continue
            text += parse_text_field(subelement)
            if subelement.tail:
                text += ' '.join(subelement.tail.split())
    if tagwrap:
        text += '&lt;/{}&gt;'.format(tag)
    if postfix:
        text += postfix
    return text


def compose_answer_key(elem, answers):
    """
    Create feedback keys for coumpoundhint tag

    :param elem: element answer is based on
    :param answers: number of checking boxes in the problem
    :return: string tuple with checked answers

    :Example:

    compoundhint = <compoundhint value="A B C">Feedback 11</compoundhint>

    compose_answer_key(compoundhint, 3) == '(1,1,1)'
    """
    key = [0 for item in range(answers)]
    for value in elem.attrib['value'].split():
        index = ord(value) - ord('A')
        key[index] = 1
    return str(tuple(key))


def create_feedback(elem, answers=0):
    """
    Create string with feedback dict

    :param elem: ElementTree element
    :param answers: number of proposed choices
    :return: string with feedback dict
    """
    feedback = u""
    if elem.tag == CHOICE_ELEMENTS[0]:
        for index, subelem in enumerate(elem.iter('choicehint')):
            feedback += parse_text_field(subelem, indent=4, prefix='{}: "'.format(index), postfix='"\n', tagwrap=False)
    elif elem.tag == CHOICE_ELEMENTS[1]:
        for subelem in elem.findall('.//compoundhint'):
            key = compose_answer_key(subelem, answers)
            feedback += parse_text_field(subelem, indent=4, prefix='{}: "'.format(key), postfix='"\n', tagwrap=False)
    return feedback


def create_answer_dict(elem, restrict_elem=None, checkbox=False):
    """
    Construct dict with choices to fulfil form's div attribute

    :param elem: ElemntTree element
    :param restrict_elem: name of element which is not included in choice text
    :param checkbox: boolean flag to work return data for checkbox problem
    :return: tuple, (constructed dict, correct_answer)
    """
    answer_dict = {}
    correct_answer = []
    for index, choice in enumerate(elem.iter('choice')):
        answer_dict['choice{}'.format(index)] = parse_text_field(choice, tagwrap=False, restrict_elem=restrict_elem)
        if choice.attrib['correct'] == 'true':
            correct_answer.append(index)
    return answer_dict, str(correct_answer if checkbox else correct_answer[0])


def prepare_answer(elem):
    if elem.tag == CHOICE_ELEMENTS[0]:
        html_file = 'generic_multiple_choice'
        restrict_elem = 'choicehint'
        answer_dict, correct_answer = create_answer_dict(elem, restrict_elem)
    elif elem.tag == CHOICE_ELEMENTS[1]:
        html_file = 'generic_checkbox'
        answer_dict, correct_answer = create_answer_dict(elem)
    return answer_dict, correct_answer, html_file


def check_problems_source(params):
    """
    Check if problems source directory or file

    :return dir_walking: boolean flag shows problems source is a dir
    """
    dir_walking = False
    if not os.path.exists(params.xmlsource):
        print("File with path: {} does not exist, please try again".format(params.xmlsource))
        sys.exit()
    elif os.path.isdir(params.xmlsource):
        dir_walking = True

    # NOTE(idegtiarov) it is required output and source directories are not the same one.
    if not os.path.exists(params.output_dir):
        os.makedirs(params.output_dir)
    elif os.path.abspath(params.output_dir) == os.path.abspath(os.path.split(params.xmlsource)[0]):
        print(
            "Output directory is the same as source one: {}. Please use different directories for source and output "
            "problems.".format(params.output_dir)
        )
        sys.exit()
    # NOTE(idegtiarov) Checking if template file exists
    if os.path.exists('capa_template.txt'):
        with open('capa_template.txt', 'r') as fh:
            capa_template = fh.read()
    else:
        print(
            "Template capa_template.txt file to create Capa problem is not found. Please add template file and try "
            "again."
        )
        sys.exit()

    return dir_walking, capa_template


def transform_problem(problem_file, output_dir, capa_template):
    """
    Problem transformation function.

    :param problem_file: path to the problem.xml file
    :param output_dir: path to output directory
    """
    tree = ET.ElementTree(file=problem_file)
    adaptive_problem = ET.Element('problem', attrib={
        'type': 'lecture', 'display_name': 'Adaptive Problem', 'showanswer': 'never'
    })

    question = u""
    for subelem in tree.getroot():
        if subelem.tag not in CHOICE_ELEMENTS:
            question += parse_text_field(subelem, indent=8, prefix='"', postfix='"\n')
        else:
            answer_dict, correct_answer, html_file = prepare_answer(subelem)
            feedback = create_feedback(subelem, answers=len(answer_dict))
            feedback_key = FEEDBACK_KEYS[subelem.tag]

    text = capa_template.format(question=question.rstrip(), feedback=feedback.rstrip(), feedback_key=feedback_key)
    script = ET.Element('script', attrib={'type': 'loncapa/python'})
    script.text = text

    text_question = ET.Element('div', attrib={'id': 'problem_text', 'text': '$text_question'})
    iframe_text_question = ET.Element(
        'iframe', attrib={
            'seamless': 'seamless',
            'id': 'first',
            'src': ('/static/js/textbox.html?user_id=$anonymous_student_id&amp;div=problem_text&amp;iframe=first&amp;'
                    'showlink=true'),
            'width': '700',
            'height': '200'
        }
    )
    number_of_answers = len(answer_dict)
    answer_dict.update({'id': 'form1', 'choices': str(number_of_answers), 'answer': correct_answer})
    form_questions = ET.Element('div', attrib=answer_dict)
    customresponse = ET.Element('customresponse', attrib={'cfn': 'vglcfn'})
    ET.SubElement(
        customresponse, 'jsinput', attrib={
            'gradefn': 'getGrade',
            'get_statefn': 'getState',
            'set_statefn': 'setState',
            'width': '700',
            'height': '160',
            'html_file': '/static/js/{}.html?user_id=$anonymous_student_id$div=form1'.format(html_file)
        }
    )
    complete_text = ET.Element(
        'iframe', attrib={
            'seamless': 'seamless',
            'id': 'complete0',
            'src': '/static/js/textbox.html?user_id=$anonymous_student_id&amp;completed=true&amp;iframe=complete0',
            'width': '700',
            'height': '1'
        }
    )

    adaptive_problem.extend(
        (script, text_question, iframe_text_question, form_questions, customresponse, complete_text)
    )
    output_file = os.path.join(output_dir, os.path.split(problem_file)[1])
    with open(output_file, 'wb') as fhandler:
        fhandler.write(pretty_print(adaptive_problem).encode('utf-8'))


def processing_problem_source(params, dir_walking, capa_template):
    """
    Processing transformation for chosen file(s) from the problems source

    :param params: argparse.Namespace object, script expected parameters
    :param dir_walking: boolean to mark source is directory
    """
    pattern = params.regex or ''

    if not dir_walking:
        return transform_problem(params.xmlsource, params.output_dir, capa_template)

    root, dirs, files = os.walk(params.xmlsource).next()
    for problem in files:
        if re.search(pattern, problem) and problem.endswith('.xml'):
            print("Transforming {} problem file".format(problem))
            transform_problem(os.path.join(root, problem), params.output_dir, capa_template)


def main():
    parameters = get_parameters()
    dir_walking, capa_template = check_problems_source(parameters)

    processing_problem_source(parameters, dir_walking, capa_template)
    print("Transformation done! Converted problems could be found in the {} directory.".format(parameters.output_dir))


if __name__ == '__main__':
    main()
