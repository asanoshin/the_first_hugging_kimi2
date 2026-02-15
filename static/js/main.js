document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const cameraInput = document.getElementById('cameraInput');
    const cameraBtn = document.getElementById('cameraBtn');
    const galleryBtn = document.getElementById('galleryBtn');
    const preview = document.getElementById('preview');
    const removeBtn = document.getElementById('removeBtn');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const promptInput = document.getElementById('promptInput');
    const errorMsg = document.getElementById('errorMsg');
    const resultCard = document.getElementById('resultCard');
    const resultText = document.getElementById('resultText');
    const usageInfo = document.getElementById('usageInfo');

    const MAX_SIZE = 10 * 1024 * 1024; // 10MB
    const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];

    let selectedFile = null;

    // Click to select file
    dropZone.addEventListener('click', (e) => {
        if (e.target === removeBtn || removeBtn.contains(e.target)) return;
        fileInput.click();
    });

    // Camera button — opens rear camera on mobile
    cameraBtn.addEventListener('click', () => cameraInput.click());

    // Gallery button — opens file picker
    galleryBtn.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFile(fileInput.files[0]);
        }
    });

    cameraInput.addEventListener('change', () => {
        if (cameraInput.files.length > 0) {
            handleFile(cameraInput.files[0]);
        }
    });

    // Drag and drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    // Remove image
    removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearImage();
    });

    function handleFile(file) {
        hideError();

        if (!ALLOWED_TYPES.includes(file.type)) {
            showError('不支援的檔案格式，僅接受 PNG、JPG、GIF、WebP');
            return;
        }

        if (file.size > MAX_SIZE) {
            showError('檔案大小超過 10MB 限制');
            return;
        }

        selectedFile = file;
        const objectUrl = URL.createObjectURL(file);
        preview.onload = () => URL.revokeObjectURL(objectUrl);
        preview.src = objectUrl;
        dropZone.classList.add('has-image');
        analyzeBtn.disabled = false;
    }

    function clearImage() {
        selectedFile = null;
        fileInput.value = '';
        cameraInput.value = '';
        preview.src = '';
        dropZone.classList.remove('has-image');
        analyzeBtn.disabled = true;
    }

    // Analyze
    analyzeBtn.addEventListener('click', async () => {
        if (!selectedFile) return;

        hideError();
        resultCard.hidden = true;
        setLoading(true);

        const formData = new FormData();
        formData.append('image', selectedFile);
        formData.append('prompt', promptInput.value);

        try {
            const res = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();

            if (!res.ok || data.error) {
                showError(data.error || '未知錯誤');
                return;
            }

            resultText.textContent = data.response;
            if (data.usage) {
                usageInfo.textContent = `Token 用量：提示 ${data.usage.prompt_tokens} + 回覆 ${data.usage.completion_tokens} = 共 ${data.usage.total_tokens}`;
            } else {
                usageInfo.textContent = '';
            }
            resultCard.hidden = false;
        } catch (err) {
            showError('請求失敗，請確認伺服器是否正在運行');
        } finally {
            setLoading(false);
        }
    });

    function setLoading(loading) {
        analyzeBtn.disabled = loading;
        analyzeBtn.classList.toggle('loading', loading);
    }

    function showError(msg) {
        errorMsg.textContent = msg;
        errorMsg.hidden = false;
    }

    function hideError() {
        errorMsg.hidden = true;
    }
});
