from .base import WysiwygWidget
from django import forms
from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.template.loader import render_to_string
from django.utils.functional import curry
from django.utils.text import mark_safe
from django.utils.translation import get_language


__all__ = ('TransStringField', 'TransWysiwygField',)


def get_field_translation(self, field):
    data = getattr(self, field.attname)
    try:
        return data.get(get_language())
    except AttributeError:
        return data.get(settings.LANGUAGE_CODE, None)


class TransWidget(forms.MultiWidget):
    template = 'utils/trans_widget.html'

    def __init__(self, widget):
        widgets = (widget,) * len(settings.LANGUAGES)
        super().__init__(widgets)

    def decompress(self, value):
        value = value or {}
        data_list = []
        for code, lang in settings.LANGUAGES:
            data_list.append(value.get(code, None))
        return data_list

    def format_output(self, rendered_widgets):
        labels = [name for code, name in settings.LANGUAGES]
        rows = list(zip(labels, rendered_widgets))
        html = render_to_string(self.template, {'rows': rows})
        return mark_safe(html)


class TextInputWidget(forms.TextInput):
    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs.setdefault('class', 'vTextField')
        super().__init__(attrs=attrs)


class TransFormField(forms.MultiValueField):
    """
    Multi language form field, required means the first language is required,
    require_all_fields means that all fields are required.
    """
    def __init__(self, label=None, max_length=None, min_length=None,
            require_all_fields=False, required=False, strip=True,
            validators=None, base_field=None, base_widget=None, *args,
            **kwargs):
        self.max_length = max_length
        self.min_length = min_length
        self.strip = strip
        self.widget = TransWidget(base_widget)
        validators = validators or []
        required_field = required or require_all_fields
        fields = []
        for code, name in settings.LANGUAGES:
            f = base_field(
                max_length=max_length, min_length=min_length,
                strip=strip, required=required_field,
                validators=validators,
                *args, **kwargs
            )
            fields.append(f)
            if not require_all_fields:
                required_field = False
        kwargs.update({
            'label': label,
            'required': required or require_all_fields,
            'require_all_fields': require_all_fields,
        })
        super().__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        data_list = data_list or []
        value = {}
        for j, v in enumerate(data_list):
            code = settings.LANGUAGES[j][0]
            value[code] = v
        return value


class TransField(JSONField):
    form_class = TransFormField
    base_field = forms.CharField
    base_widget = TextInputWidget
    max_length = None

    def __init__(self, verbose_name=None, max_length=None, required=False,
            require_all_fields=False, form_class=None, base_field=None,
            base_widget=None, **kwargs):
        self.formfield_defaults = {
            'base_field': base_field or self.base_field,
            'base_widget': base_widget or self.base_widget,
            'form_class': form_class or self.form_class,
            'max_length': max_length or self.max_length,
            'require_all_fields': require_all_fields
        }
        defaults = {
            'blank': not required,
            'null': not required,
            'verbose_name': verbose_name,
            'max_length': max_length,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs.pop('max_length', None)  # remove all kwargs not applicable for JSONField
        return name, 'django.contrib.postgres.fields.jsonb.JSONField', args, kwargs

    def formfield(self, **kwargs):
        defaults = self.formfield_defaults.copy()
        defaults.update(**kwargs)
        return super().formfield(**defaults)

    def contribute_to_class(self, cls, *args, **kwargs):
        super().contribute_to_class(cls, *args, **kwargs)
        if self.column:
            attr = self.attname.rsplit('_', 1)[0]
            if not getattr(cls, attr, None):
                setattr(cls, attr, property(curry(get_field_translation, field=self)))


# ~~~~~~~~~~~
# StringField
# ~~~~~~~~~~~
class TransStringField(TransField):
    max_length = 255


# ~~~~~~~~~~~~
# WysiwygField
# ~~~~~~~~~~~~
class TransWysiwygField(TransField):
    base_widget = WysiwygWidget


# ~~~~~~~~
# TagField
# ~~~~~~~~
#class TransTagFormField(TransField):
#    widget = TransWidget(TextInputWidget)
#
#
#class TransTagField(TransField):
#    form_class = TransTagFormField