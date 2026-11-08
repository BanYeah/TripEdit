from datetime import date
from zipfile import ZipFile
from pathlib import Path
from scripts.check_gtfs_date import check_day


def test_calendar_and_exception_dates(tmp_path):
    out=tmp_path/'feed.zip'
    with ZipFile(out,'w') as z:
        z.writestr('calendar.txt', 'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nWK,1,1,1,1,1,0,0,20260101,20261231\n')
        z.writestr('calendar_dates.txt', 'service_id,date,exception_type\nWK,20261110,2\nWK,20261114,1\n')
        z.writestr('trips.txt','route_id,service_id,trip_id\nR,WK,T\n')
    assert check_day(out,date(2026,11,9))['date_covered']
    assert not check_day(out,date(2026,11,10))['date_covered']
    assert check_day(out,date(2026,11,14))['date_covered']
