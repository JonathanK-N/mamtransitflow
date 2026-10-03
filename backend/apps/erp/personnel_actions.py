from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from . import models as m
from .messaging import MessagingView, direct_conversation
from .personnel import remove_employee


class EmployeeActionView(MessagingView):
    def post(self,request,pk,action):
        self.ensure('employees')
        if self.member.role not in ('owner','admin'):raise PermissionDenied('Administration requise.')
        employee=get_object_or_404(m.Employee,organization=self.org,pk=pk)
        if action=='remove':
            remove_employee(self.org,self.member,employee)
            return Response({'ok':True,'active':False})
        colleague=m.Membership.objects.filter(organization=self.org,user_id=employee.user_id,active=True,user__is_active=True).first() if employee.user_id and employee.active else None
        if not colleague:raise ValidationError("Ce membre du personnel n'a pas encore de compte TransitFlow actif.")
        row,created=direct_conversation(self.member,colleague,request.user)
        return Response(self.summary(row),status=201 if created else 200)
