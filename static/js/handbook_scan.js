document.addEventListener('DOMContentLoaded', () => {
    // State
    let sessionId = null;
    let currentStep = 1;
    let mpersonid = null;
    let patientName = null;
    let staffName = '';
    let currentReviewPageId = null;
    let pollingTimer = null;

    const PAGE_TYPE_LABELS = {
        'basic_info': '健保卡',
        'parent_record': '家長紀錄事項',
        'health_education': '衛教指導紀錄',
        'unknown': '未知'
    };

    const AGE_STAGES = {
        1: '出生至二個月', 2: '二至四個月', 3: '四至十個月',
        4: '十個月至一歲半', 5: '一歲半至二歲', 6: '二至三歲', 7: '三至未滿七歲'
    };

    // Elements
    const steps = document.querySelectorAll('.hb-step');
    const stepPanels = {
        1: document.getElementById('step1'),
        2: document.getElementById('step2'),
        3: document.getElementById('step3'),
        4: document.getElementById('step4'),
    };

    // --- Step Navigation ---
    function goToStep(n) {
        currentStep = n;
        steps.forEach(s => {
            const sn = parseInt(s.dataset.step);
            s.classList.remove('active', 'done');
            if (sn < n) s.classList.add('done');
            if (sn === n) s.classList.add('active');
        });
        Object.entries(stepPanels).forEach(([k, panel]) => {
            panel.classList.toggle('hb-hidden', parseInt(k) !== n);
        });
    }

    // --- Step 1: 員工登入 ---
    document.getElementById('startSessionBtn').addEventListener('click', async () => {
        staffName = document.getElementById('staffName').value.trim();
        if (!staffName) { alert('請輸入姓名'); return; }

        try {
            const res = await fetch('/handbook/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scanned_by: staffName })
            });
            const data = await res.json();
            if (!res.ok) { alert(data.error); return; }
            sessionId = data.session_id;
            goToStep(2);
        } catch (err) {
            alert('無法建立工作階段');
        }
    });

    // --- Step 2: 健保卡辨識 ---
    const icFileInput = document.getElementById('icFileInput');
    const icCameraInput = document.getElementById('icCameraInput');

    document.getElementById('icCameraBtn').addEventListener('click', () => icCameraInput.click());
    document.getElementById('icGalleryBtn').addEventListener('click', () => icFileInput.click());
    document.getElementById('insuranceCardZone').addEventListener('click', () => icFileInput.click());

    icFileInput.addEventListener('change', () => { if (icFileInput.files[0]) uploadInsuranceCard(icFileInput.files[0]); });
    icCameraInput.addEventListener('change', () => { if (icCameraInput.files[0]) uploadInsuranceCard(icCameraInput.files[0]); });

    async function uploadInsuranceCard(file) {
        document.getElementById('icProcessing').classList.remove('hb-hidden');
        document.getElementById('icResult').classList.add('hb-hidden');

        const formData = new FormData();
        formData.append('images', file);

        try {
            const res = await fetch(`/handbook/sessions/${sessionId}/pages`, {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (!res.ok) { alert(data.error); return; }

            // Poll for result
            const pageId = data.page_ids[0];
            await pollPageResult(pageId, (page) => {
                document.getElementById('icProcessing').classList.add('hb-hidden');
                document.getElementById('icResult').classList.remove('hb-hidden');

                const extracted = page.ocr_extracted_json || {};
                document.getElementById('patientName').value = extracted.name || '';
                document.getElementById('patientId').value = extracted.id_number || '';

                // 自動比對病人
                if (extracted.id_number) {
                    lookupPatient(extracted.id_number);
                }
            });
        } catch (err) {
            document.getElementById('icProcessing').classList.add('hb-hidden');
            alert('上傳失敗');
        }
    }

    async function lookupPatient(idNumber) {
        try {
            const res = await fetch(`/handbook/patients/search?q=${encodeURIComponent(idNumber)}`);
            const data = await res.json();
            const banner = document.getElementById('patientBanner');
            if (data.results && data.results.length > 0 && data.results[0].found !== false) {
                const p = data.results[0];
                banner.innerHTML = `
                    <div class="hb-patient-banner">
                        <span class="icon">✅</span>
                        <div class="info">
                            <strong>已找到：${esc(p.name)}</strong>
                            <span>${esc(p.mpersonid)} | ${p.sex === 'M' ? '男' : p.sex === 'F' ? '女' : ''} | 生日：${esc(p.birth_date || '')}</span>
                        </div>
                    </div>`;
                patientName = p.name;
            } else {
                banner.innerHTML = `
                    <div class="hb-patient-banner not-found">
                        <span class="icon">⚠️</span>
                        <div class="info">
                            <strong>系統中無此病人</strong>
                            <span>請確認身分證字號是否正確</span>
                        </div>
                    </div>`;
            }
        } catch (err) {
            console.error('Lookup error:', err);
        }
    }

    document.getElementById('confirmPatientBtn').addEventListener('click', async () => {
        const idVal = document.getElementById('patientId').value.trim();
        if (!idVal) { alert('請輸入身分證字號'); return; }
        mpersonid = idVal;
        patientName = patientName || document.getElementById('patientName').value.trim();

        // 確認健保卡 page
        const statusRes = await fetch(`/handbook/sessions/${sessionId}/status`);
        const statusData = await statusRes.json();
        const icPage = statusData.pages.find(p => p.page_type === 'basic_info');
        if (icPage) {
            await fetch(`/handbook/pages/${icPage.id}/confirm`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    confirmed_by: staffName,
                    corrections: { id_number: mpersonid, name: patientName }
                })
            });
        }

        showStep3PatientInfo();
        goToStep(3);
    });

    document.getElementById('retakeIcBtn').addEventListener('click', () => {
        document.getElementById('icResult').classList.add('hb-hidden');
        icFileInput.value = '';
        icCameraInput.value = '';
    });

    document.getElementById('skipIcBtn').addEventListener('click', () => {
        const manualId = prompt('請輸入病人身分證字號：');
        if (!manualId) return;
        mpersonid = manualId.trim();
        lookupPatient(mpersonid).then(() => {
            patientName = patientName || '';
            showStep3PatientInfo();
            goToStep(3);
        });
    });

    function showStep3PatientInfo() {
        if (mpersonid) {
            document.getElementById('step3PatientInfo').classList.remove('hb-hidden');
            document.getElementById('step3PatientName').textContent = patientName || '未知';
            document.getElementById('step3PatientIdDisplay').textContent = mpersonid;
        }
    }

    // --- Step 3: 掃描手冊頁面 ---
    const pageFileInput = document.getElementById('pageFileInput');
    const pageCameraInput = document.getElementById('pageCameraInput');

    document.getElementById('pageCameraBtn').addEventListener('click', () => pageCameraInput.click());
    document.getElementById('pageGalleryBtn').addEventListener('click', () => pageFileInput.click());
    document.getElementById('pageUploadZone').addEventListener('click', () => pageFileInput.click());

    pageFileInput.addEventListener('change', () => {
        if (pageFileInput.files.length > 0) uploadPages(pageFileInput.files);
    });
    pageCameraInput.addEventListener('change', () => {
        if (pageCameraInput.files.length > 0) uploadPages(pageCameraInput.files);
    });

    async function uploadPages(files) {
        const formData = new FormData();
        for (const file of files) {
            formData.append('images', file);
        }

        document.getElementById('ocrProgress').classList.remove('hb-hidden');
        updateProgress(0, files.length);

        try {
            const res = await fetch(`/handbook/sessions/${sessionId}/pages`, {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (!res.ok) { alert(data.error); return; }

            // Start polling
            startPolling();
        } catch (err) {
            alert('上傳失敗');
        }

        pageFileInput.value = '';
        pageCameraInput.value = '';
    }

    function startPolling() {
        if (pollingTimer) clearInterval(pollingTimer);
        pollingTimer = setInterval(pollSessionStatus, 3000);
        pollSessionStatus();
    }

    async function pollSessionStatus() {
        try {
            const res = await fetch(`/handbook/sessions/${sessionId}/status`);
            const data = await res.json();

            // Filter out basic_info pages (already handled in step 2)
            const pages = data.pages.filter(p => p.page_type !== 'basic_info' || p.status === 'confirmed');
            const handbookPages = data.pages.filter(p => p.page_type !== 'basic_info');
            const completed = handbookPages.filter(p => p.status === 'ocr_complete' || p.status === 'confirmed');

            updateProgress(completed.length, handbookPages.length);
            renderPageQueue(handbookPages);

            // Show first unreviewed result
            const unreviewed = handbookPages.find(p => p.status === 'ocr_complete');
            if (unreviewed && unreviewed.id !== currentReviewPageId) {
                showReview(unreviewed);
            }

            // Stop polling if all done
            if (handbookPages.length > 0 && completed.length === handbookPages.length) {
                if (pollingTimer) { clearInterval(pollingTimer); pollingTimer = null; }
            }
        } catch (err) {
            console.error('Poll error:', err);
        }
    }

    function updateProgress(done, total) {
        if (total === 0) return;
        const pct = Math.round((done / total) * 100);
        document.getElementById('progressFill').style.width = pct + '%';
        document.getElementById('progressText').textContent = `處理中 ${done}/${total}...`;
        if (done === total) {
            document.getElementById('progressText').textContent = `全部完成 ${total}/${total}`;
        }
    }

    function renderPageQueue(pages) {
        const queue = document.getElementById('pageQueue');
        if (pages.length === 0) { queue.innerHTML = ''; return; }

        queue.innerHTML = pages.map(p => `
            <div class="hb-page-item ${p.id === currentReviewPageId ? 'active' : ''}" data-page-id="${p.id}">
                <div class="page-num">${p.page_order}</div>
                <div class="page-info">
                    <div class="type">${PAGE_TYPE_LABELS[p.page_type] || '處理中...'}</div>
                </div>
                <span class="hb-status">
                    <span class="hb-status-dot ${p.status === 'ocr_processing' ? 'processing' : p.status === 'ocr_complete' ? 'complete' : p.status === 'confirmed' ? 'confirmed' : p.status === 'rejected' ? 'rejected' : 'pending'}"></span>
                    ${statusLabel(p.status)}
                </span>
            </div>
        `).join('');

        // Click to review
        queue.querySelectorAll('.hb-page-item').forEach(el => {
            el.addEventListener('click', () => {
                const pid = parseInt(el.dataset.pageId);
                const page = pages.find(p => p.id === pid);
                if (page && (page.status === 'ocr_complete' || page.status === 'confirmed')) {
                    showReview(page);
                }
            });
        });
    }

    function statusLabel(status) {
        const map = {
            'pending': '等待中',
            'ocr_processing': '辨識中',
            'ocr_complete': '待確認',
            'confirmed': '已確認',
            'rejected': '已拒絕'
        };
        return map[status] || status;
    }

    function showReview(page) {
        currentReviewPageId = page.id;
        const area = document.getElementById('reviewArea');
        area.classList.remove('hb-hidden');
        document.getElementById('reviewPageType').textContent = PAGE_TYPE_LABELS[page.page_type] || '未知';

        const content = document.getElementById('reviewContent');
        const data = page.ocr_extracted_json;

        if (!data) {
            content.innerHTML = '<p style="color:#dc3545;">OCR 無法解析此頁面</p>';
            return;
        }

        if (page.page_type === 'parent_record') {
            content.innerHTML = renderParentRecordReview(data);
        } else if (page.page_type === 'health_education') {
            content.innerHTML = renderHealthEducationReview(data);
        } else {
            content.innerHTML = `<pre style="font-size:0.85rem; overflow:auto;">${esc(JSON.stringify(data, null, 2))}</pre>`;
        }

        // Scroll to review
        area.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function renderParentRecordReview(data) {
        const items = data.checklist_items || [];
        return `
            <div style="margin-bottom:0.75rem;">
                <span class="hb-badge hb-badge-info">第${data.visit_number || '?'}次</span>
                <span style="margin-left:0.5rem; font-size:0.9rem;">${esc(data.age_stage || '')}</span>
                ${data.record_date ? `<span style="margin-left:0.5rem; font-size:0.85rem; color:#666;">日期：${esc(data.record_date)}</span>` : ''}
            </div>
            <ul class="hb-checklist" id="reviewChecklist">
                ${items.map((item, i) => `
                    <li>
                        ${item['是警訊'] ? '<span class="warning">※</span>' : '<span style="width:16px;"></span>'}
                        <span class="category">${esc(item['類別'] || '')}</span>
                        <span class="question">${esc(item['題目'])}</span>
                        <span class="answer">
                            <label><input type="radio" name="item_${i}" value="是" ${item['結果'] === '是' ? 'checked' : ''}> 是</label>
                            <label><input type="radio" name="item_${i}" value="否" ${item['結果'] === '否' ? 'checked' : ''}> 否</label>
                        </span>
                    </li>
                `).join('')}
            </ul>
            ${data.parent_notes ? `<div style="margin-top:0.75rem;"><label class="hb-label">備註</label><input type="text" class="hb-input" id="reviewParentNotes" value="${esc(data.parent_notes)}"></div>` : ''}
        `;
    }

    function renderHealthEducationReview(data) {
        const pa = data.parent_assessment || [];
        const dg = data.doctor_guidance || [];
        return `
            <div style="margin-bottom:0.75rem;">
                <span class="hb-badge hb-badge-info">第${data.visit_number || '?'}次</span>
                <span style="margin-left:0.5rem; font-size:0.9rem;">${esc(data.age_stage || '')}</span>
                ${data.guidance_date ? `<span style="margin-left:0.5rem; font-size:0.85rem; color:#666;">日期：${esc(data.guidance_date)}</span>` : ''}
            </div>
            ${pa.length ? `
                <h3 style="font-size:0.9rem; color:#1E3A5F; margin:1rem 0 0.5rem;">家長評估</h3>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem;">
                    ${pa.map((a, i) => `
                        <div style="padding:0.4rem 0.75rem; background:#f8f9fa; border-radius:6px; font-size:0.85rem;">
                            <label><input type="checkbox" id="pa_${i}" ${a['已做到'] ? 'checked' : ''}> ${esc(a['主題'])}</label>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
            ${dg.length ? `
                <h3 style="font-size:0.9rem; color:#1E3A5F; margin:1rem 0 0.5rem;">醫師指導重點</h3>
                ${dg.map((g, gi) => `
                    <div class="hb-guidance-group">
                        <h4>${esc(g['主題'])} - ${esc(g['重點'] || '')}</h4>
                        ${(g['項目'] || []).map((item, ii) => `
                            <div class="hb-guidance-item">
                                <input type="checkbox" id="dg_${gi}_${ii}" ${item['已勾'] ? 'checked' : ''}>
                                <span>${esc(item['內容'])}</span>
                            </div>
                        `).join('')}
                    </div>
                `).join('')}
            ` : ''}
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.75rem; margin-top:1rem;">
                <div>
                    <label class="hb-label">醫療院所代碼</label>
                    <input type="text" class="hb-input" id="reviewHospital" value="${esc(data.hospital_code || '')}">
                </div>
                <div>
                    <label class="hb-label">醫師</label>
                    <input type="text" class="hb-input" id="reviewDoctor" value="${esc(data.doctor_name || '')}">
                </div>
            </div>
        `;
    }

    // Confirm page
    document.getElementById('confirmPageBtn').addEventListener('click', async () => {
        if (!currentReviewPageId) return;

        // Collect corrections from the review form
        const corrections = collectCorrections();

        try {
            const res = await fetch(`/handbook/pages/${currentReviewPageId}/confirm`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    confirmed_by: staffName,
                    corrections: corrections
                })
            });
            const data = await res.json();
            if (!res.ok) { alert(data.error); return; }

            document.getElementById('reviewArea').classList.add('hb-hidden');
            currentReviewPageId = null;
            pollSessionStatus();
        } catch (err) {
            alert('確認失敗');
        }
    });

    // Reject page
    document.getElementById('rejectPageBtn').addEventListener('click', async () => {
        if (!currentReviewPageId) return;

        try {
            await fetch(`/handbook/pages/${currentReviewPageId}/reject`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' }
            });
            document.getElementById('reviewArea').classList.add('hb-hidden');
            currentReviewPageId = null;
            pollSessionStatus();
        } catch (err) {
            alert('操作失敗');
        }
    });

    function collectCorrections() {
        // Try to read modified values from the review form
        // For parent_record: read radio buttons
        const checklist = document.getElementById('reviewChecklist');
        if (checklist) {
            const items = [];
            checklist.querySelectorAll('li').forEach((li, i) => {
                const radios = li.querySelectorAll(`input[name="item_${i}"]`);
                let result = '未勾選';
                radios.forEach(r => { if (r.checked) result = r.value; });

                const question = li.querySelector('.question')?.textContent || '';
                const category = li.querySelector('.category')?.textContent || '';
                const isWarning = !!li.querySelector('.warning');
                items.push({
                    '題目': question,
                    '類別': category,
                    '結果': result,
                    '是警訊': isWarning
                });
            });
            const notes = document.getElementById('reviewParentNotes');
            return {
                checklist_items: items,
                parent_notes: notes ? notes.value : null
            };
        }

        // For health_education
        const hospitalEl = document.getElementById('reviewHospital');
        if (hospitalEl) {
            return {
                hospital_code: hospitalEl.value,
                doctor_name: document.getElementById('reviewDoctor')?.value || ''
            };
        }

        return null;
    }

    // Finish scan
    document.getElementById('finishScanBtn').addEventListener('click', async () => {
        if (pollingTimer) { clearInterval(pollingTimer); pollingTimer = null; }

        try {
            await fetch(`/handbook/sessions/${sessionId}/complete`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' }
            });
        } catch (err) {
            console.error(err);
        }

        document.getElementById('summaryText').textContent =
            `已完成 ${patientName || ''} (${mpersonid || ''}) 的手冊掃描`;
        goToStep(4);
    });

    // --- Helpers ---
    async function pollPageResult(pageId, callback) {
        const maxAttempts = 60; // 3 min max
        for (let i = 0; i < maxAttempts; i++) {
            await sleep(3000);
            try {
                const res = await fetch(`/handbook/sessions/${sessionId}/status`);
                const data = await res.json();
                const page = data.pages.find(p => p.id === pageId);
                if (page && (page.status === 'ocr_complete' || page.status === 'confirmed')) {
                    callback(page);
                    return;
                }
            } catch (err) {
                console.error(err);
            }
        }
        alert('OCR 處理逾時，請重試');
    }

    function sleep(ms) {
        return new Promise(r => setTimeout(r, ms));
    }

    function esc(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    }
});
