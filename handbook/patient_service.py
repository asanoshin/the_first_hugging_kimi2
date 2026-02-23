"""病人比對服務 - 查詢 basic_raw_data_table"""

from sqlalchemy import text
from models import SessionLocal


def search_patient_by_id(mpersonid):
    """用身分證字號查詢 basic_raw_data_table"""
    db = SessionLocal()
    try:
        result = db.execute(
            text("SELECT mpersonid, mname, msex, mbirthdt, mtelh, mrec "
                 "FROM basic_raw_data_table WHERE mpersonid = :pid LIMIT 1"),
            {"pid": mpersonid}
        ).fetchone()
        if result:
            return {
                'mpersonid': result[0],
                'name': result[1],
                'sex': result[2],
                'birth_date': result[3],
                'phone_home': result[4],
                'phone_mobile': result[5],
                'found': True
            }
        return {'found': False, 'mpersonid': mpersonid}
    finally:
        db.close()


def search_patient_by_name(name):
    """用姓名模糊搜尋 basic_raw_data_table"""
    db = SessionLocal()
    try:
        results = db.execute(
            text("SELECT mpersonid, mname, msex, mbirthdt, mtelh, mrec "
                 "FROM basic_raw_data_table WHERE mname LIKE :name "
                 "ORDER BY mname LIMIT 20"),
            {"name": f"%{name}%"}
        ).fetchall()
        return [
            {
                'mpersonid': r[0],
                'name': r[1],
                'sex': r[2],
                'birth_date': r[3],
                'phone_home': r[4],
                'phone_mobile': r[5],
            }
            for r in results
        ]
    finally:
        db.close()
