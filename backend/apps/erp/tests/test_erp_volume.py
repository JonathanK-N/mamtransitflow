from datetime import timedelta
from time import perf_counter

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.erp import models as m
from .test_workflows import env

pytestmark=pytest.mark.django_db


def test_erp_volume_keeps_tenant_queries_and_pagination_bounded(env,record_property):
    def measure(path):
        started=perf_counter()
        with CaptureQueriesContext(connection) as queries:
            result=env['client'].get('/api/v2/'+path)
        assert result.status_code==200,result.data
        return result,len(queries),(perf_counter()-started)*1000
    paths=['clients','orders','missions','operations/center','dashboard']
    baseline={path:measure(path)[1] for path in paths}
    customers=m.Partner.objects.bulk_create([m.Partner(organization=env['org'],name=f'TEST Volume client {n:04d}') for n in range(1000)])
    vehicles=m.Vehicle.objects.bulk_create([m.Vehicle(organization=env['org'],plate=f'TEST-VOL-{n}',name='Camion TEST') for n in range(100)])
    drivers=m.Employee.objects.bulk_create([m.Employee(organization=env['org'],name=f'TEST Chauffeur {n}',job='driver') for n in range(200)])
    today=timezone.localdate()
    orders=m.TransportOrder.objects.bulk_create([m.TransportOrder(organization=env['org'],reference=f'TEST-CMD-{n}',customer=customers[n%1000],origin='A',destination='B',planned_date=today,amount='100.01',status='completed') for n in range(5000)])
    departure=timezone.now()-timedelta(days=2)
    m.Mission.objects.bulk_create([m.Mission(organization=env['org'],reference=f'TEST-MIS-{n}',order=orders[n],vehicle=vehicles[n%100],driver=drivers[n%200],origin='A',destination='B',departure=departure,arrival=departure+timedelta(hours=1),completed_at=departure+timedelta(hours=1),status='completed',loaded_quantity=1,delivered_quantity=1) for n in range(5000)])
    for path in paths:
        response,count,duration=measure(path)
        # Empty collections need no serializer queries; allow a fixed page overhead.
        assert count<=baseline[path]+5 and count<=40,(path,baseline[path],count)
        if path in ('clients','orders','missions'):
            assert len(response.data['results'])<=25
            assert response.data['count']==(1001 if path=='clients' else 5000)
        record_property(path.replace('/','_')+'_sql_queries',count)
        record_property(path.replace('/','_')+'_milliseconds',round(duration,2))
    record_property('volume','1000 clients, 5000 orders, 5000 missions, 100 vehicles, 200 drivers added to isolated fixtures')
