from django.contrib import admin

from .models import Debate, DebateMessage


class DebateMessageInline(admin.TabularInline):
    model = DebateMessage
    extra = 0
    readonly_fields = ('side', 'content', 'offset_seconds')
    can_delete = False


@admin.register(Debate)
class DebateAdmin(admin.ModelAdmin):
    list_display = ('theme', 'created_date', 'duration_seconds')
    readonly_fields = ('summary',)
    inlines = [DebateMessageInline]
