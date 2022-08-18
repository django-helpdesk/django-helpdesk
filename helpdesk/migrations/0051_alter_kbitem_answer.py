# Generated by Django 3.2.7 on 2022-01-28 17:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0050_auto_20220118_1015'),
    ]

    operations = [
        migrations.AlterField(
            model_name='kbitem',
            name='answer',
            field=models.TextField(help_text='<a href="http://daringfireball.net/projects/markdown/syntax" target="_blank">Markdown syntax</a> allowed, but no raw HTML. Examples: **bold**, *italic*, indent 4 spaces for a code block.<br/><br/><b>Multple newlines:</b><br/>Markdown doesn\'t recognize multiple blank lines. To display one, write &amp;nbsp; on a blank line.<br/><br/><b>Table formatting:</b><br/><pre>First Header  | Second Header</br>------------- | -------------</br>Content Cell  | Content Cell</br>Content Cell  | Content Cell</pre></br><b>Collapsing section:</b><br/> Add !~! on a line following the section title, followed by a blank line. Add ~!~ on a line following the section body, followed by another blank line. <br/>The body may have multiple lines of text, but no blank lines.<br/><br/>Example:<br/><pre>This text comes before the section.<br/><br/>Title of Subsection<br/>!~!<br/><br/>&amp;nbsp;<br/>Body of subsection.<br/>&amp;nbsp;<br/>I can add many lines of text to this. It will all be included in the section.<br/>~!~<br/><br/>&amp;nbsp;<br/>This, however, won\'t be included in the collapsing section.</pre>', verbose_name='Answer'),
        ),
    ]