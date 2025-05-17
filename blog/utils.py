# blog/utils.py
from .models import Tag

def get_tag_index_map():
    tags = Tag.objects.order_by('slug').values_list('slug', flat=True)
    return { slug: i for i, slug in enumerate(tags) }
