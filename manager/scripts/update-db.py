from director.apps.sites.models import DatabaseHost

remove_databases = [
    {'hostname': 'postgres', 'port': 5432},
    {'hostname': 'mysql', 'port': 3306},
]
for data in remove_databases:
    DatabaseHost.objects.filter(**data).delete()

databases = [
    {
        'hostname': 'postgres',
        'port': 5432,
        'dbms': 'postgres',
        'admin_hostname': 'localhost',
        'admin_port': 5433,
        'admin_username': 'postgres',
        'admin_password': 'pwd',
    },
    {
        'hostname': 'mysql',
        'port': 3306,
        'dbms': 'mysql',
        'admin_hostname': '127.0.0.1',
        'admin_port': 3307,
        'admin_username': 'root',
        'admin_password': 'pwd',
    },
]

for data in databases:
    q = DatabaseHost.objects.filter(hostname=data['hostname'], port=data['port'])
    if q.exists():
        assert q.count() == 1, 'Please delete duplicate DatabaseHosts'
        q.update(**data)
    else:
        DatabaseHost.objects.create(**data)
