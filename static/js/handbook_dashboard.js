document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const searchResults = document.getElementById('searchResults');

    // 搜尋病人
    searchBtn.addEventListener('click', searchPatients);
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') searchPatients();
    });

    async function searchPatients() {
        const q = searchInput.value.trim();
        if (!q) return;

        searchResults.innerHTML = '<p style="color:#999; text-align:center;">搜尋中...</p>';

        try {
            const res = await fetch(`/handbook/patients/search?q=${encodeURIComponent(q)}`);
            const data = await res.json();

            if (!data.results || data.results.length === 0) {
                searchResults.innerHTML = '<p style="color:#999; text-align:center; padding:1rem;">查無結果</p>';
                return;
            }

            searchResults.innerHTML = `
                <table class="hb-table">
                    <thead>
                        <tr>
                            <th>姓名</th>
                            <th>身分證號</th>
                            <th>性別</th>
                            <th>出生日期</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.results.map(p => `
                            <tr>
                                <td>${esc(p.name)}</td>
                                <td>${esc(p.mpersonid)}</td>
                                <td>${p.sex === 'M' ? '男' : p.sex === 'F' ? '女' : esc(p.sex || '')}</td>
                                <td>${esc(p.birth_date || '')}</td>
                                <td><a href="/handbook/patients/${encodeURIComponent(p.mpersonid)}">查看紀錄</a></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>`;
        } catch (err) {
            searchResults.innerHTML = '<p style="color:#dc3545;">搜尋失敗，請稍後再試</p>';
        }
    }

    function esc(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    }
});
