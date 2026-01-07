// Configuración
const API_BASE = window.location.origin;

// Dashboard functions
if (window.location.pathname === '/' || window.location.pathname === '/index.html') {
    document.addEventListener('DOMContentLoaded', function() {
        loadStats();
        setInterval(loadStats, 5000);
        
        document.getElementById('codigoInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') validateTicket();
        });
    });
    
    async function validateTicket() {
        const code = document.getElementById('codigoInput').value.trim();
        if (!code) return;
        
        try {
            const response = await fetch(`${API_BASE}/api/validar/${code}`);
            const data = await response.json();
            
            const resultDiv = document.getElementById('resultado');
            resultDiv.innerHTML = `
                <div class="${data.estado === 'valido' ? 'result-valid' : 'result-invalid'}">
                    <h3>${data.estado === 'valido' ? '✅ VÁLIDO' : '❌ INVÁLIDO'}</h3>
                    <p>${data.mensaje}</p>
                    ${data.datos_boleto ? `
                        <p><strong>Cliente:</strong> ${data.datos_boleto.nombre_cliente || 'N/A'}</p>
                        <p><strong>Evento:</strong> ${data.datos_boleto.evento || 'N/A'}</p>
                    ` : ''}
                </div>
            `;
            
            loadStats();
            
        } catch (error) {
            document.getElementById('resultado').innerHTML = `
                <div class="result-error">
                    <p>Error: ${error.message}</p>
                </div>
            `;
        }
    }
    
    async function loadStats() {
        try {
            const response = await fetch(`${API_BASE}/api/estadisticas`);
            const data = await response.json();
            
            const stats = data.estadisticas;
            document.getElementById('estadisticas').innerHTML = `
                <div class="stat-item">
                    <div class="stat-number">${stats.total_boletos}</div>
                    <div class="stat-label">TOTAL</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">${stats.validados}</div>
                    <div class="stat-label">VALIDADOS</div>
                    <div>${stats.porcentaje_validado}%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">${stats.pendientes}</div>
                    <div class="stat-label">PENDIENTES</div>
                </div>
            `;
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }
}

// Mobile scanner functions
if (window.location.pathname === '/scanner') {
    let videoStream = null;
    let scanning = false;
    
    document.addEventListener('DOMContentLoaded', function() {
        document.getElementById('codigoManual').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') validateManual();
        });
    });
    
    async function toggleCamera() {
        if (!videoStream) {
            try {
                videoStream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: 'environment' }
                });
                
                const video = document.getElementById('video');
                video.srcObject = videoStream;
                video.play();
                
                document.getElementById('cameraBtn').textContent = '⏸ DETENER';
                document.getElementById('cameraBtn').className = 'btn btn-danger';
                
                startScanning();
                
            } catch (error) {
                alert('Error al acceder a la cámara: ' + error.message);
            }
        } else {
            stopCamera();
        }
    }
    
    function stopCamera() {
        if (videoStream) {
            videoStream.getTracks().forEach(track => track.stop());
            videoStream = null;
            document.getElementById('video').srcObject = null;
            document.getElementById('cameraBtn').textContent = '▶ INICIAR CÁMARA';
            document.getElementById('cameraBtn').className = 'btn btn-primary';
            scanning = false;
        }
    }
    
    function startScanning() {
        scanning = true;
        const video = document.getElementById('video');
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        function scan() {
            if (!scanning || !videoStream) return;
            
            if (video.readyState === video.HAVE_ENOUGH_DATA) {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                const code = jsQR(imageData.data, imageData.width, imageData.height);
                
                if (code) {
                    stopCamera();
                    validateCode(code.data);
                }
            }
            
            requestAnimationFrame(scan);
        }
        
        scan();
    }
    
    async function validateCode(code) {
        try {
            const response = await fetch(`${API_BASE}/api/validar/${code}?dispositivo=mobile`);
            const data = await response.json();
            
            showResult(data);
            
            if (navigator.vibrate) {
                navigator.vibrate(data.estado === 'valido' ? [100, 50, 100] : [300, 100, 300]);
            }
            
        } catch (error) {
            showResult({
                estado: 'error',
                mensaje: 'Error de conexión'
            });
        }
    }
    
    function validateManual() {
        const code = document.getElementById('codigoManual').value.trim();
        if (code) {
            validateCode(code);
            document.getElementById('codigoManual').value = '';
        }
    }
    
    function showResult(data) {
        const card = document.getElementById('resultadoCard');
        
        card.className = 'result-card show';
        card.style.background = data.estado === 'valido' ? '#d4edda' : '#f8d7da';
        card.style.color = data.estado === 'valido' ? '#155724' : '#721c24';
        
        card.innerHTML = `
            <h3>${data.estado === 'valido' ? '✅ VÁLIDO' : '❌ INVÁLIDO'}</h3>
            <p>${data.mensaje}</p>
            ${data.datos_boleto ? `
                <p><strong>Cliente:</strong> ${data.datos_boleto.nombre_cliente || 'N/A'}</p>
                <p><strong>Asiento:</strong> ${data.datos_boleto.asiento || 'N/A'}</p>
            ` : ''}
            <button class="btn btn-primary" onclick="resetScanner()" style="margin-top: 15px;">
                🔄 ESCANEAR OTRO
            </button>
        `;
        
        card.scrollIntoView({ behavior: 'smooth' });
    }
    
    function resetScanner() {
        document.getElementById('resultadoCard').classList.remove('show');
        toggleCamera();
    }
}