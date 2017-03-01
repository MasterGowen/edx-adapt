# Script to transform problem into adaptive capa problem

Currently script supports transformation for two main problems:
`Multiple Choice` and `Checkbox`.
For example Checkbox problem:

```xml
<problem display_name="Did I Get This" showanswer="never">
  <p>Question text</p>
  <choiceresponse>
    <checkboxgroup>
      <choice correct="false">Answer1</choice>
      <choice correct="true">Answer2</choice>
      <choice correct="true">Answer3</choice>
      <compoundhint value="A">Feedback 1</compoundhint>
      <compoundhint value="B">Feedback 2</compoundhint>
      <compoundhint value="C">Feedback 3</compoundhint>
      <compoundhint value="D">Feedback 4</compoundhint>
      <compoundhint value="A B">Feedback 5</compoundhint>
      <compoundhint value="A C">Feedback 6</compoundhint>
      <compoundhint value="B C">Feedback 8</compoundhint>
      <compoundhint value="A B C">Feedback 11</compoundhint>
    </checkboxgroup>
  </choiceresponse>
</problem>
```

Would be transform into adaptive capa problem:

```xml
<problem display_name="Adaptive Problem" showanswer="never" type="lecture">
  <script type="loncapa/python">
import json

feedback = {
    (1, 0, 0): &quot;Feedback 1&quot;
    (0, 1, 0): &quot;Feedback 2&quot;
    (0, 0, 1): &quot;Feedback 3&quot;
    (1, 1, 0): &quot;Feedback 5&quot;
    (1, 0, 1): &quot;Feedback 6&quot;
    (0, 1, 1): &quot;Feedback 8&quot;
    (1, 1, 1): &quot;Feedback 11&quot;
}

# Answer checking function called when the user hits &quot;Check&quot;
def vglcfn(e, ans):
    # Here we load the dictionary that EdX creates from the return
    # values of GetState() and GetGrade()
    par = json.loads(ans);
    # Then we pull out and parse the return value from GetGrade(). The
    # value from GetState() is in par[&quot;state&quot;]
    answer = json.loads(par[&quot;answer&quot;])
    # In our case the boolean value named correct_answer is true if
    # the student got the question right
    return {
        'input_list': [
            { 'ok': answer['correct_answer'], 'msg': feedback[tuple(answer['inputs'])},
        ]
    }

    text_question = (
        &quot;&amp;lt;p&amp;gt;Question text&amp;lt;/p&amp;gt;&quot;
    )
    </script>
  <div id="problem_text" text="$text_question"/>
  <iframe height="200" id="first" seamless="seamless" src="/static/js/textbox.html?user_id=$anonymous_student_id&amp;
  amp;div=problem_text&amp;amp;iframe=first&amp;amp;showlink=true" width="700"/>
  <div answer="1" choice0="Answer1" choice1="Answer2" choice2="Answer3"
   choices="3" id="form1"/>
  <customresponse cfn="vglcfn">
    <jsinput get_statefn="getState" gradefn="getGrade" height="160" html_file="/static/js/generic_checkbox.html?
    user_id=$anonymous_student_id$div=form1" set_statefn="setState" width="700"/>
  </customresponse>
  <iframe height="1" id="complete0" seamless="seamless" src="/static/js/textbox.html?user_id=$anonymous_student_id&amp;
  amp;completed=true&amp;amp;iframe=complete0" width="700"/>
</problem>
```

Script usage:

```bash
> python transform_problems.py path/to/problem/xml/file/source path/to/output/dir [--regex 'string to search in file name']
```

Where `--regex` is optional parameter with expect string to select
matched files from source problem dirs.

E.g. source directory has four problem files:

```text
--problem
  |--section1-problem1.xml
  |--section1-problem2.xml
  |--chap-info.xml
  |--data_info.xml
```

with `--regex section` first two problem will be transformed, with
`--regex _info` only last one.
