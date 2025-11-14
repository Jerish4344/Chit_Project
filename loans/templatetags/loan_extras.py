from django import template

register = template.Library()

@register.filter
def total_amount(queryset, field_name):
    return sum(getattr(obj, field_name, 0) for obj in queryset)
