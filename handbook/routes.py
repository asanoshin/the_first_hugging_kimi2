"""兒童健康手冊 OCR 數位化 - API 路由"""

import base64
import threading
from datetime import datetime, timezone, date
from flask import render_template, request, jsonify

from handbook import handbook_bp
from models import (SessionLocal, HandbookScanSession, HandbookScannedPage,
                    HandbookParentRecord, HandbookHealthEducation)
from handbook.ocr_service import process_page
from handbook.patient_service import search_patient_by_id, search_patient_by_name

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MIME_MAP = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
            'gif': 'image/gif', 'webp': 'image/webp'}


def _get_mime(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpeg'
    return MIME_MAP.get(ext, 'image/jpeg')


# --- 頁面路由 ---

@handbook_bp.route('/')
def dashboard():
    return render_template('dashboard.html')


@handbook_bp.route('/scan')
def scan_page():
    return render_template('scan.html')


@handbook_bp.route('/patients/<mpersonid>')
def patient_detail(mpersonid):
    return render_template('patient_detail.html', mpersonid=mpersonid)


# --- API 路由 ---

@handbook_bp.route('/sessions', methods=['POST'])
def create_session():
    """開始新掃描工作階段"""
    data = request.get_json() or {}
    scanned_by = data.get('scanned_by', '').strip()
    if not scanned_by:
        return jsonify({'error': '請輸入員工姓名'}), 400

    db = SessionLocal()
    try:
        session = HandbookScanSession(scanned_by=scanned_by, status='in_progress')
        db.add(session)
        db.commit()
        db.refresh(session)
        return jsonify({
            'session_id': session.id,
            'status': session.status,
            'scanned_by': session.scanned_by
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


def _process_page_async(page_id):
    """背景處理單張頁面 OCR"""
    db = SessionLocal()
    try:
        page = db.query(HandbookScannedPage).get(page_id)
        if not page or not page.image_data:
            return

        page.status = 'ocr_processing'
        db.commit()

        mime_type = 'image/jpeg'
        # image_data 欄位儲存的是 "mime_type|base64data" 格式
        if '|' in page.image_data[:50]:
            mime_type, b64_data = page.image_data.split('|', 1)
        else:
            b64_data = page.image_data

        result = process_page(b64_data, mime_type)

        page.page_type = result['page_type']
        page.ocr_raw_response = result.get('raw_response', '')
        page.ocr_extracted_json = result.get('extracted_data')
        page.status = 'ocr_complete' if result['extracted_data'] else 'pending'
        db.commit()
    except Exception as e:
        page.status = 'pending'
        page.ocr_raw_response = f'Error: {str(e)}'
        db.commit()
    finally:
        db.close()


@handbook_bp.route('/sessions/<int:session_id>/pages', methods=['POST'])
def upload_pages(session_id):
    """上傳照片（支援批次多張），觸發排隊 OCR"""
    db = SessionLocal()
    try:
        session = db.query(HandbookScanSession).get(session_id)
        if not session:
            return jsonify({'error': '找不到工作階段'}), 404

        files = request.files.getlist('images')
        if not files:
            return jsonify({'error': '請上傳至少一張照片'}), 400

        existing_count = db.query(HandbookScannedPage).filter_by(
            session_id=session_id
        ).count()

        page_ids = []
        for i, file in enumerate(files):
            if not file or not file.filename:
                continue
            image_data = file.read()
            b64 = base64.b64encode(image_data).decode('utf-8')
            mime = _get_mime(file.filename)

            page = HandbookScannedPage(
                session_id=session_id,
                page_order=existing_count + i + 1,
                status='pending',
                image_data=f"{mime}|{b64}"
            )
            db.add(page)
            db.flush()
            page_ids.append(page.id)

        db.commit()

        # 逐一啟動背景 OCR 處理
        for pid in page_ids:
            thread = threading.Thread(target=_process_page_async, args=(pid,))
            thread.daemon = True
            thread.start()

        return jsonify({
            'uploaded': len(page_ids),
            'page_ids': page_ids
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@handbook_bp.route('/sessions/<int:session_id>/status')
def session_status(session_id):
    """查詢批次 OCR 處理進度"""
    db = SessionLocal()
    try:
        session = db.query(HandbookScanSession).get(session_id)
        if not session:
            return jsonify({'error': '找不到工作階段'}), 404

        pages = db.query(HandbookScannedPage).filter_by(
            session_id=session_id
        ).order_by(HandbookScannedPage.page_order).all()

        return jsonify({
            'session_id': session_id,
            'mpersonid': session.mpersonid,
            'status': session.status,
            'total_pages': len(pages),
            'completed': sum(1 for p in pages if p.status in ('ocr_complete', 'confirmed')),
            'pages': [
                {
                    'id': p.id,
                    'page_order': p.page_order,
                    'page_type': p.page_type,
                    'status': p.status,
                    'ocr_extracted_json': p.ocr_extracted_json,
                    'has_image': bool(p.image_data),
                }
                for p in pages
            ]
        })
    finally:
        db.close()


@handbook_bp.route('/pages/<int:page_id>/confirm', methods=['PUT'])
def confirm_page(page_id):
    """員工確認/修正 OCR 結果並存檔"""
    db = SessionLocal()
    try:
        page = db.query(HandbookScannedPage).get(page_id)
        if not page:
            return jsonify({'error': '找不到頁面'}), 404

        data = request.get_json() or {}
        confirmed_by = data.get('confirmed_by', '')
        corrections = data.get('corrections')
        final_data = corrections if corrections else page.ocr_extracted_json

        # 取得 session 來獲得 mpersonid
        session = db.query(HandbookScanSession).get(page.session_id)
        mpersonid = session.mpersonid if session else None

        if page.page_type == 'basic_info':
            # 健保卡辨識 - 更新 session 的 mpersonid
            id_number = final_data.get('id_number', '') if final_data else ''
            if id_number and session:
                session.mpersonid = id_number
                db.commit()

        elif page.page_type == 'parent_record' and mpersonid and final_data:
            visit_number = final_data.get('visit_number', 0)
            record_date = _parse_date(final_data.get('record_date'))

            existing = db.query(HandbookParentRecord).filter_by(
                mpersonid=mpersonid, visit_number=visit_number
            ).first()

            if existing:
                existing.age_stage = final_data.get('age_stage')
                existing.record_date = record_date
                existing.checklist_items = final_data.get('checklist_items')
                existing.parent_notes = final_data.get('parent_notes')
            else:
                record = HandbookParentRecord(
                    mpersonid=mpersonid,
                    visit_number=visit_number,
                    age_stage=final_data.get('age_stage'),
                    record_date=record_date,
                    checklist_items=final_data.get('checklist_items'),
                    parent_notes=final_data.get('parent_notes'),
                )
                db.add(record)

        elif page.page_type == 'health_education' and mpersonid and final_data:
            visit_number = final_data.get('visit_number', 0)
            guidance_date = _parse_date(final_data.get('guidance_date'))

            existing = db.query(HandbookHealthEducation).filter_by(
                mpersonid=mpersonid, visit_number=visit_number
            ).first()

            if existing:
                existing.age_stage = final_data.get('age_stage')
                existing.guidance_date = guidance_date
                existing.parent_assessment = final_data.get('parent_assessment')
                existing.doctor_guidance = final_data.get('doctor_guidance')
                existing.hospital_code = final_data.get('hospital_code')
                existing.doctor_name = final_data.get('doctor_name')
                existing.relationship = final_data.get('relationship')
            else:
                edu = HandbookHealthEducation(
                    mpersonid=mpersonid,
                    visit_number=visit_number,
                    age_stage=final_data.get('age_stage'),
                    guidance_date=guidance_date,
                    parent_assessment=final_data.get('parent_assessment'),
                    doctor_guidance=final_data.get('doctor_guidance'),
                    hospital_code=final_data.get('hospital_code'),
                    doctor_name=final_data.get('doctor_name'),
                    relationship=final_data.get('relationship'),
                )
                db.add(edu)

        page.status = 'confirmed'
        page.confirmed_by = confirmed_by
        page.staff_corrections = corrections
        page.image_data = None  # 確認後清空暫存圖片
        db.commit()

        return jsonify({'success': True, 'page_id': page_id})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


def _parse_date(date_str):
    """嘗試解析日期字串"""
    if not date_str:
        return None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


@handbook_bp.route('/pages/<int:page_id>/reject', methods=['PUT'])
def reject_page(page_id):
    """拒絕 OCR 結果，需重新掃描"""
    db = SessionLocal()
    try:
        page = db.query(HandbookScannedPage).get(page_id)
        if not page:
            return jsonify({'error': '找不到頁面'}), 404
        page.status = 'rejected'
        page.image_data = None
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@handbook_bp.route('/patients/search')
def search_patients():
    """搜尋病人"""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'results': []})

    # 判斷是身分證號還是姓名
    if len(q) == 10 and q[0].isalpha():
        patient = search_patient_by_id(q)
        if patient.get('found'):
            return jsonify({'results': [patient]})
        return jsonify({'results': []})
    else:
        results = search_patient_by_name(q)
        return jsonify({'results': results})


@handbook_bp.route('/patients/<mpersonid>/records')
def patient_records(mpersonid):
    """查看病人的手冊紀錄"""
    db = SessionLocal()
    try:
        parent_records = db.query(HandbookParentRecord).filter_by(
            mpersonid=mpersonid
        ).order_by(HandbookParentRecord.visit_number).all()

        health_edu = db.query(HandbookHealthEducation).filter_by(
            mpersonid=mpersonid
        ).order_by(HandbookHealthEducation.visit_number).all()

        patient = search_patient_by_id(mpersonid)

        return jsonify({
            'patient': patient,
            'parent_records': [
                {
                    'id': r.id,
                    'visit_number': r.visit_number,
                    'age_stage': r.age_stage,
                    'record_date': r.record_date.isoformat() if r.record_date else None,
                    'checklist_items': r.checklist_items,
                    'parent_notes': r.parent_notes,
                    'created_at': r.created_at.isoformat() if r.created_at else None,
                }
                for r in parent_records
            ],
            'health_education': [
                {
                    'id': e.id,
                    'visit_number': e.visit_number,
                    'age_stage': e.age_stage,
                    'guidance_date': e.guidance_date.isoformat() if e.guidance_date else None,
                    'parent_assessment': e.parent_assessment,
                    'doctor_guidance': e.doctor_guidance,
                    'hospital_code': e.hospital_code,
                    'doctor_name': e.doctor_name,
                    'relationship': e.relationship,
                    'created_at': e.created_at.isoformat() if e.created_at else None,
                }
                for e in health_edu
            ]
        })
    finally:
        db.close()


@handbook_bp.route('/sessions/<int:session_id>/complete', methods=['PUT'])
def complete_session(session_id):
    """完成掃描工作階段"""
    db = SessionLocal()
    try:
        session = db.query(HandbookScanSession).get(session_id)
        if not session:
            return jsonify({'error': '找不到工作階段'}), 404
        session.status = 'completed'
        session.completed_at = datetime.now(timezone.utc)
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
