document_ready(() => {
    // Session State variables
    let sessionId = null;
    let userName = "";
    let userDomain = "";
    let interviewMode = "";
    let currentQuestionNum = 1;
    let totalQuestionsCount = 5;
    let selectedFile = null;
    let competencyChart = null;

    // Element cache
    const screenSetup = document.getElementById("screen-setup");
    const screenChat = document.getElementById("screen-chat");
    const screenDashboard = document.getElementById("screen-dashboard");

    const setupForm = document.getElementById("setup-form");
    const fileDropArea = document.getElementById("file-drop-area");
    const inputResume = document.getElementById("input-resume");
    const fileNameDisplay = document.getElementById("file-name-display");
    const fileNameText = document.getElementById("file-name-text");
    const btnRemoveFile = document.getElementById("btn-remove-file");

    const displayName = document.getElementById("display-name");
    const displayDomain = document.getElementById("display-domain");
    const displayMode = document.getElementById("display-mode");
    const statusSkillMatcher = document.getElementById("status-skill-matcher");
    const statusSkillEval = document.getElementById("status-skill-eval");
    const currentQNum = document.getElementById("current-q-num");
    const totalQNum = document.getElementById("total-q-num");
    const progressFill = document.getElementById("progress-fill");

    const chatMessages = document.getElementById("chat-messages");
    const typingIndicator = document.getElementById("typing-indicator");
    const chatInput = document.getElementById("chat-input");
    const btnSend = document.getElementById("btn-send");

    const metricAvgScore = document.getElementById("metric-avg-score");
    const metricDomain = document.getElementById("metric-domain");
    const weakspotsContainer = document.getElementById("weakspots-container");
    const feedbackAccordion = document.getElementById("feedback-accordion");
    const btnRestart = document.getElementById("btn-restart");

    /* =========================================================================
       1. Setup File Ingestion Handlers
       ========================================================================= */
    
    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        fileDropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Highlight drop zone when item is dragged over
    ['dragenter', 'dragover'].forEach(eventName => {
        fileDropArea.addEventListener(eventName, () => fileDropArea.classList.add('drag-over'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        fileDropArea.addEventListener(eventName, () => fileDropArea.classList.remove('drag-over'), false);
    });

    // Handle dropped files
    fileDropArea.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });

    // Handle file selection via click/browse
    inputResume.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    function handleFileSelect(file) {
        const validExtensions = ['.pdf', '.txt'];
        const fileName = file.name;
        const isExtensionValid = validExtensions.some(ext => fileName.toLowerCase().endsWith(ext));

        if (!isExtensionValid) {
            alert("Invalid file format. Please upload a PDF or TXT file.");
            return;
        }

        selectedFile = file;
        fileNameText.textContent = fileName;
        fileDropArea.classList.add('hidden');
        fileNameDisplay.classList.remove('hidden');
    }

    btnRemoveFile.addEventListener('click', () => {
        selectedFile = null;
        inputResume.value = "";
        fileNameDisplay.classList.add('hidden');
        fileDropArea.classList.remove('hidden');
    });


    /* =========================================================================
       2. Session Start Handling
       ========================================================================= */
    
    setupForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Get values
        userName = document.getElementById("input-name").value.trim();
        userDomain = document.getElementById("input-domain").value.trim();
        interviewMode = document.getElementById("select-mode").value;
        const jdText = document.getElementById("textarea-jd").value.trim();

        // Prepare FormData
        const formData = new FormData();
        formData.append("name", userName);
        formData.append("domain", userDomain);
        formData.append("mode", interviewMode);
        formData.append("jd_text", jdText);

        if (selectedFile) {
            formData.append("resume_file", selectedFile);
        } else {
            formData.append("resume_text", "No resume uploaded.");
        }

        // Disable start button
        const btnStart = document.getElementById("btn-start");
        btnStart.disabled = true;
        btnStart.querySelector('.btn-text').textContent = "Ingesting Profile & Initializing Graph...";

        try {
            const response = await fetch("/api/session/start", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Failed to initialize coach session.");
            }

            const data = await response.json();

            // Set session states
            sessionId = data.session_id;
            totalQuestionsCount = data.total_questions;
            currentQuestionNum = 1;

            // Populate Sidebar
            displayName.textContent = userName;
            displayDomain.textContent = userDomain;
            displayMode.textContent = interviewMode;
            currentQNum.textContent = currentQuestionNum;
            totalQNum.textContent = totalQuestionsCount;
            updateProgress(0);

            // Toggle matcher skill status active during initialization
            statusSkillMatcher.classList.add("active");

            // Switch to Chat Screen
            switchScreen(screenChat);

            // Clear chat and append first question
            clearChatMessages();
            appendCoachMessage("Resume & Job Description parsed successfully. Skills mounted.");
            
            // Show typing indicator before displaying the first question
            showTypingIndicator();
            setTimeout(() => {
                hideTypingIndicator();
                appendCoachMessage(data.first_question);
                chatInput.disabled = false;
                chatInput.focus();
                btnSend.disabled = false;
            }, 1200);

        } catch (error) {
            alert(`Error: ${error.message}`);
            btnStart.disabled = false;
            btnStart.querySelector('.btn-text').textContent = "Start Coach Session";
        }
    });

    /* =========================================================================
       3. Chat Loop Handling
       ========================================================================= */

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    chatInput.addEventListener('input', () => {
        btnSend.disabled = chatInput.value.trim() === "";
    });

    btnSend.addEventListener('click', sendMessage);

    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text || !sessionId) return;

        // Clear input & disable
        chatInput.value = "";
        chatInput.disabled = true;
        btnSend.disabled = true;

        // Append candidate message
        appendCandidateMessage(text);

        // Show typing indicator
        showTypingIndicator();

        // Prepare FormData
        const formData = new FormData();
        formData.append("session_id", sessionId);
        formData.append("user_answer", text);

        try {
            const response = await fetch("/api/session/chat", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Server error while processing answer.");
            }

            const data = await response.json();

            // Toggle evaluator status if behavioral mode or active evaluation
            statusSkillEval.classList.add("active");

            hideTypingIndicator();

            // Render feedback and scores
            let feedbackText = `📊 **Evaluation Score**: ${data.score}/10\n\n_${data.feedback}_`;
            appendCoachMessage(feedbackText);

            if (data.finished) {
                // Show completion summary message
                appendCoachMessage("Session complete! Moving to the evaluation dashboard...");
                
                setTimeout(() => {
                    loadDashboard();
                }, 2000);
            } else {
                // Increment question count
                currentQuestionNum++;
                currentQNum.textContent = currentQuestionNum;
                updateProgress((currentQuestionNum - 1) / totalQuestionsCount);

                // Show typing indicator before displaying the next question
                showTypingIndicator();
                setTimeout(() => {
                    hideTypingIndicator();
                    appendCoachMessage(data.question);
                    chatInput.disabled = false;
                    chatInput.focus();
                    btnSend.disabled = false;
                }, 1500);
            }

        } catch (error) {
            hideTypingIndicator();
            alert(`Error: ${error.message}`);
            chatInput.disabled = false;
            chatInput.focus();
            btnSend.disabled = false;
        }
    }

    /* =========================================================================
       4. Dashboard & Analytics Visualization
       ========================================================================= */

    async function loadDashboard() {
        try {
            const response = await fetch(`/api/session/analytics?session_id=${sessionId}`);
            if (!response.ok) throw new Error("Failed to load analytics data.");

            const data = await response.json();

            // Render metric summaries
            metricAvgScore.textContent = data.average_score;
            metricDomain.textContent = data.domain;

            // Render persistent weak spots
            weakspotsContainer.innerHTML = "";
            if (data.weakspots.length === 0) {
                weakspotsContainer.innerHTML = `<p class="section-desc">No major weaknesses identified. Great job!</p>`;
            } else {
                data.weakspots.forEach(item => {
                    const tag = document.createElement("div");
                    tag.className = "weakspot-tag";
                    tag.innerHTML = `
                        <span>${item.topic}</span>
                        <span class="weakspot-rating">${item.rating}/10</span>
                    `;
                    weakspotsContainer.appendChild(tag);
                });
            }

            // Render detailed feedback accordion log
            feedbackAccordion.innerHTML = "";
            data.history.forEach((item, index) => {
                const accItem = document.createElement("div");
                accItem.className = `accordion-item ${index === 0 ? 'open' : ''}`;
                
                accItem.innerHTML = `
                    <div class="accordion-header">
                        <span class="accordion-title">Q${index+1}: ${item.question}</span>
                        <span class="accordion-score-badge">${item.score}/10</span>
                        <span class="accordion-arrow">▼</span>
                    </div>
                    <div class="accordion-content">
                        <div class="feedback-section">
                            <h4>Coaching Feedback</h4>
                            <p>${item.feedback}</p>
                        </div>
                    </div>
                `;

                // Add click listener to toggle accordion
                accItem.querySelector(".accordion-header").addEventListener("click", () => {
                    accItem.classList.toggle("open");
                });

                feedbackAccordion.appendChild(accItem);
            });

            // Initialize or update competencies Radar Chart
            renderCompetencyChart(data.competency_scores);

            // Switch to Dashboard Screen
            switchScreen(screenDashboard);

        } catch (error) {
            alert(`Failed to render dashboard: ${error.message}`);
        }
    }

    function renderCompetencyChart(scores) {
        const ctx = document.getElementById('chart-competencies').getContext('2d');
        
        const labels = Object.keys(scores);
        const dataValues = Object.values(scores);

        if (competencyChart) {
            competencyChart.destroy();
        }

        // Chart styling configurations
        competencyChart = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Competency Level',
                    data: dataValues,
                    backgroundColor: 'rgba(190, 90, 50, 0.15)',
                    borderColor: 'rgba(190, 90, 50, 0.85)',
                    pointBackgroundColor: 'rgb(190, 90, 50)',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: 'rgb(190, 90, 50)',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        angleLines: {
                            color: 'rgba(255, 255, 255, 0.08)'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.08)'
                        },
                        pointLabels: {
                            color: '#e2e8f0',
                            font: {
                                family: 'Inter',
                                size: 11
                            }
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.4)',
                            backdropColor: 'transparent',
                            beginAtZero: true,
                            max: 10,
                            stepSize: 2
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    /* =========================================================================
       5. Navigation & UI Helpers
       ========================================================================= */

    function switchScreen(targetScreen) {
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.remove('active');
        });
        targetScreen.classList.add('active');
    }

    function appendCoachMessage(text) {
        // Convert simple markdown styling (like **, _) to html tags
        const formattedText = text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/_(.*?)_/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');

        const msg = document.createElement("div");
        msg.className = "message coach";
        msg.innerHTML = `
            <div class="message-avatar">✦</div>
            <div class="message-content">
                <p>${formattedText}</p>
            </div>
        `;
        chatMessages.appendChild(msg);
        scrollToBottom();
    }

    function appendCandidateMessage(text) {
        const msg = document.createElement("div");
        msg.className = "message candidate";
        msg.innerHTML = `
            <div class="message-avatar">U</div>
            <div class="message-content">
                <p>${text.replace(/\n/g, '<br>')}</p>
            </div>
        `;
        chatMessages.appendChild(msg);
        scrollToBottom();
    }

    function showTypingIndicator() {
        typingIndicator.classList.remove("hidden");
        scrollToBottom();
    }

    function hideTypingIndicator() {
        typingIndicator.classList.add("hidden");
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function updateProgress(ratio) {
        progressFill.style.width = `${ratio * 100}%`;
    }

    function clearChatMessages() {
        // Remove all child messages except the static welcome and typing indicator
        const messages = Array.from(chatMessages.querySelectorAll('.message'));
        messages.forEach(msg => {
            if (msg !== typingIndicator && !msg.classList.contains('coach') || msg.innerText.includes("analyze")) {
                msg.remove();
            }
        });
    }

    btnRestart.addEventListener('click', () => {
        // Reset state variables
        sessionId = null;
        selectedFile = null;
        inputResume.value = "";
        
        // Reset file display
        fileNameDisplay.classList.add('hidden');
        fileDropArea.classList.remove('hidden');

        // Reset Setup Form fields
        document.getElementById("input-name").value = "";
        document.getElementById("input-domain").value = "";
        document.getElementById("textarea-jd").value = "";
        
        // Reset Sidebar indicators
        statusSkillMatcher.classList.remove("active");
        statusSkillEval.classList.remove("active");

        // Re-enable Start button text
        const btnStart = document.getElementById("btn-start");
        btnStart.disabled = false;
        btnStart.querySelector('.btn-text').textContent = "Start Coach Session";

        // Switch screen back to setup
        switchScreen(screenSetup);
    });

});

// Helper for DOM content loaded wrapper
function document_ready(fn) {
    if (document.readyState !== 'loading') {
        fn();
    } else {
        document.addEventListener('DOMContentLoaded', fn);
    }
}
