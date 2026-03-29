from django.urls import path

from . import views

urlpatterns = [
    path('group/create/', views.create_group, name='create_group'),
    path('member/create/', views.create_member, name='create_member'),
    path('members/', views.all_members, name='all_members'),
    path('member/<int:member_id>/edit-details/', views.edit_member_details, name='edit_member_details'),
    path('member/<int:member_id>/delete/', views.delete_member, name='delete_member'),
    path('group/<int:group_id>/print/', views.group_print, name='group_print'),
    path('group/<int:group_id>/edit/', views.edit_group, name='edit_group'),
    path('group/<int:group_id>/delete/', views.delete_group, name='delete_group'),
    path('group/<int:group_id>/members/', views.edit_members, name='edit_members'),
    path('group/<int:group_id>/members/add/', views.add_membership, name='add_membership'),
    path('group/<int:group_id>/member/<int:member_id>/edit/', views.edit_member, name='edit_member'),
    path('group/<int:group_id>/member/<int:membership_id>/book/', views.member_book, name='member_book'),
    path('group/<int:group_id>/schedules/', views.edit_schedules, name='edit_schedules'),
    path('group/<int:group_id>/schedule/<int:schedule_id>/edit/', views.edit_schedule, name='edit_schedule'),
    path('group/<int:group_id>/rounds/', views.edit_rounds, name='edit_rounds'),
    path('group/<int:group_id>/round/<int:round_id>/edit/', views.edit_round, name='edit_round'),
    path('', views.dashboard, name='dashboard'),
    path('<int:group_id>/', views.dashboard, name='dashboard_group'),
    path('<int:group_id>/add-round/', views.add_round, name='add_round'),
    path('<int:group_id>/save-payment/', views.save_payment, name='save_payment'),
]
