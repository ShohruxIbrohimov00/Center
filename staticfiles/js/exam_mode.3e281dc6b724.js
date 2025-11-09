// exam_mode.js
// Bu fayl Digital SAT (DSAT) va Subject Exam (Mavzu Imtihoni) rejimlarini boshqarish uchun ishlatiladi.

// =================================================================
// Global O'zgaruvchilar va DOM Elementlari
// IS_SUBJECT_EXAM, ATTEMPT_ID, CSRF_TOKEN, SECTION_ATTEMPTS_DATA kabi 
// o'zgaruvchilar HTML / Django kontekstidan o'tishi kerak!
// =================================================================

const timerElement = document.getElementById('timer');
const hideTimerBtn = document.getElementById('hide-timer-btn');
const calculatorBtn = document.getElementById('calculator-btn');
const referenceBtn = document.getElementById('reference-btn');
const directionsBtn = document.getElementById('directions-btn');

const exitExamBtn = document.getElementById('exit-btn');
const confirmFinishModal = document.getElementById('confirm-exit-modal');
const confirmFinishYesBtn = document.getElementById('final-finish-btn');

const nextBtn = document.getElementById('next-btn');
const prevBtn = document.getElementById('prev-btn');
const navGrid = document.getElementById('question-nav-grid');
const markReviewBtn = document.getElementById('mark-review-btn');
const questionNumberEl = document.getElementById('question-number');
const navModalBtn = document.getElementById('nav-btn');

const questionTextEl = document.getElementById('question-text');
const questionImageContainer = document.getElementById('question-image-container');
const questionImageEl = document.getElementById('question-image');
const answerOptionsContainer = document.getElementById('answer-options-container');
const questionNumberHeaderEl = document.getElementById('question-number-header'); // Header sarlavhasi

// Global Holat O'zgaruvchilari
let questionIds = [];
let currentQuestionIndex = 0;
let answeredQuestionIds = new Set();
let reviewedQuestionIds = new Set();
let timerInterval;
let syncTimerInterval; 
let desmosLoaded = false; 
let lastSyncTime = 0; 

// LocalStorage kalitlari
const STORAGE_KEYS = {
    TIME_REMAINING: 'exam_time_remaining',
    CURRENT_SECTION: 'exam_current_section',
    LAST_SYNC: 'exam_last_sync'
};

// =================================================================
// YORDAMCHI FUNKSIYALAR
// =================================================================

function formatTime(totalSeconds) {
    if (totalSeconds < 0) totalSeconds = 0;
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    
    if (totalSeconds < 300) { 
        timerElement?.classList.add('text-red-500', 'font-bold');
    } else {
        timerElement?.classList.remove('text-red-500', 'font-bold');
    }
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function toggleTimerVisibility() {
    if (timerElement) {
        timerElement.classList.toggle('hidden');
        hideTimerBtn.textContent = timerElement.classList.contains('hidden') ? 'Show' : 'Hide';
    }
}

// LocalStorage ga saqlash va tiklash
function saveToLocalStorage() {
    localStorage.setItem(STORAGE_KEYS.TIME_REMAINING, timeRemaining.toString());
    localStorage.setItem(STORAGE_KEYS.CURRENT_SECTION, currentSectionId);
    localStorage.setItem(STORAGE_KEYS.LAST_SYNC, Date.now().toString());
}

function loadFromLocalStorage() {
    const savedTime = localStorage.getItem(STORAGE_KEYS.TIME_REMAINING);
    const savedSection = localStorage.getItem(STORAGE_KEYS.CURRENT_SECTION);
    if (savedTime && !isNaN(parseInt(savedTime))) {
        timeRemaining = parseInt(savedTime);
    }
    if (savedSection && SECTION_ATTEMPTS_DATA[savedSection]) {
        currentSectionId = savedSection;
    }
    lastSyncTime = parseInt(localStorage.getItem(STORAGE_KEYS.LAST_SYNC) || '0');
}

/**
 * Javob variantlari UI holatini yangilash.
 */
function updateOptionUI(optionItem, isSelected) {
    const input = optionItem.querySelector('input');
    if(input) input.checked = isSelected;

    if (isSelected) {
        optionItem.classList.add('selected', 'border-blue-500', 'bg-blue-50');
        optionItem.classList.remove('border-gray-200');
    } else {
        optionItem.classList.remove('selected', 'border-blue-500', 'bg-blue-50');
        optionItem.classList.add('border-gray-200');
    }

    const customElement = optionItem.querySelector('.custom-radio') || optionItem.querySelector('.custom-checkbox');
    if (customElement) {
        if (isSelected) {
            customElement.classList.add('bg-blue-600', 'border-blue-600');
            customElement.classList.remove('border-gray-400');
            customElement.innerHTML = '<svg class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20"><path d="M0 11l2-2 5 5L18 3l2 2L7 18z"/></svg>';
        } else {
            customElement.classList.remove('bg-blue-600', 'border-blue-600');
            customElement.classList.add('border-gray-400');
            customElement.innerHTML = '';
        }
    }
}

/**
 * HTML Teglarni Tozalash (MathJax renderlashdan oldin)
 */
function cleanOptionText(element) {
    function decodeHtml(html) {
        var txt = document.createElement("textarea");
        txt.innerHTML = html;
        return txt.value;
    }

    element.querySelectorAll('.option-text').forEach(span => {
        let content = span.innerHTML;
        content = decodeHtml(decodeHtml(content)); 

        const pTagRegex = /^\s*<p>(.*?)<\/p>\s*$/is; 
        const match = content.match(pTagRegex);
        
        if (match && match[1]) {
            content = match[1].trim(); 
        }
        
        span.innerHTML = content;
    });
}

// =================================================================
// TAYMER VA SERVER SINXRONIZATSIYASI
// =================================================================

function startTimer() {
    if (timerInterval) clearInterval(timerInterval);
    if (syncTimerInterval) clearInterval(syncTimerInterval);

    if (timerElement && timeRemaining !== undefined && timeRemaining >= 0) {
        timerElement.textContent = formatTime(timeRemaining);
        
        timerInterval = setInterval(async () => {
            if (timeRemaining <= 0) {
                clearInterval(timerInterval);
                timerElement.textContent = "00:00";
                // Mavzu testi bo'lsa darhol yakunlash
                const action = (typeof IS_SUBJECT_EXAM !== 'undefined' && IS_SUBJECT_EXAM) ? 'finish_exam' : 'finish_section';
                handleFinishAction(action); 
            } else {
                timeRemaining--;
                timerElement.textContent = formatTime(timeRemaining);
                saveToLocalStorage(); // Har soniyada local saqlash

                // Tarmoq onlayn bo'lsa, har 30 soniyada sinxronlash (debounce)
                if (navigator.onLine && Date.now() - lastSyncTime > 30000) {
                    await syncTimer();
                    lastSyncTime = Date.now();
                }
            }
        }, 1000);
    } else {
        console.error("Timer ishga tushmadi: timeRemaining aniqlanmadi yoki noto‘g‘ri", timeRemaining);
    }
}

async function syncTimer() {
    try {
        await fetch(EXAM_AJAX_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
            body: JSON.stringify({
                action: 'sync_timer', 
                attempt_id: ATTEMPT_ID,
                section_attempt_id: currentSectionId,
                time_remaining: timeRemaining,
            })
        });
    } catch (error) {
        console.warn("Taymer sinxronizatsiyasida xato:", error);
        showError("Tarmoq aloqasi uzildi. Vaqt local saqlanmoqda. Qayta ulanganda sinxronlashadi.");
    }
}

// Tarmoq holatini kuzatish
window.addEventListener('online', () => {
    console.log('Tarmoq qayta ulandi');
    syncTimer(); // Qayta ulanganda darhol sinxronlash
});
window.addEventListener('offline', () => {
    console.log('Tarmoq uzildi');
});

// Sahifa chiqilganda saqlash
window.addEventListener('beforeunload', () => {
    saveToLocalStorage();
    if (timerInterval) clearInterval(timerInterval);
});

// =================================================================
// TUGMA BOSHQARUVI VA NAVIGATSIYA MANTIQI
// =================================================================

/**
 * 🔥 O'ZGARTIRILDI: NEXT tugmasini Mavzu Testi uchun "Finish Exam" ga o'zgartirish.
 */
function updateNavigationButtons() {
    prevBtn.disabled = (currentQuestionIndex === 0);

    const totalQuestions = questionIds.length;
    const isLastQuestion = currentQuestionIndex === totalQuestions - 1;

    // NEXT tugmasini yangilash
    if (isLastQuestion) {
        // Mavzu Testi uchun (bitta bo'lim = butun imtihon)
        if (typeof IS_SUBJECT_EXAM !== 'undefined' && IS_SUBJECT_EXAM) {
            nextBtn.innerHTML = '<span class="nav-btn-text">Imtihonni Yakunlash</span> <i class="fa-solid fa-check"></i>';
            nextBtn.dataset.action = 'finish_exam';
        } else {
            // To'liq SAT Testi uchun
            nextBtn.innerHTML = '<span class="nav-btn-text">Keyingi Bo\'lim</span> <i class="fa-solid fa-chevron-right"></i>';
            nextBtn.dataset.action = 'finish_section';
        }
    } else {
        // Oddiy 'Next'
        nextBtn.innerHTML = '<span class="nav-btn-text">Next</span> <i class="fa-solid fa-chevron-right"></i>';
        nextBtn.dataset.action = 'next_question';
    }
    nextBtn.disabled = false;
}


async function handleNextOrFinish() {
    await saveAnswer(true);

    const totalQuestions = questionIds.length;
    
    // Agar oxirgi savol bo'lmasa, keyingisiga o'tish
    if (currentQuestionIndex < totalQuestions - 1) {
        currentQuestionIndex++;
        await loadQuestion(questionIds[currentQuestionIndex]);
    } else {
        // Agar oxirgi savol bo'lsa, actionni aniqlash
        const action = (typeof IS_SUBJECT_EXAM !== 'undefined' && IS_SUBJECT_EXAM) ? 'finish_exam' : 'finish_section';
        
        // Agar finish_exam bo'lsa, modalni ochish (handleNextOrFinish ni chaqirmasdan modal ochish mantiqi to'g'riroq)
        if (action === 'finish_exam') {
             // Odatda bu mantiqni nextBtn event listener ichida hal qilish maqsadga muvofiq,
             // Lekin bu yerda to'g'ridan-to'g'ri handleNextOrFinish() chaqirilganda ham ishlashi uchun.
             openModal('confirm-exit-modal');
        } else {
            // SAT uchun keyingi bo'limga o'tish
            await handleFinishAction(action); 
        }
    }

    updateNavigationButtons();
}

async function handleFinishAction(action) {
    // Stop all timers to prevent further execution
    if (timerInterval) clearInterval(timerInterval);
    if (syncTimerInterval) clearInterval(syncTimerInterval);
    
    // closeModal('confirm-exit-modal'); // Yakunlash modalini yopish

    try {
        const response = await fetch(EXAM_AJAX_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify({
                action: action,
                attempt_id: ATTEMPT_ID,
                section_attempt_id: currentSectionId,
                time_remaining: timeRemaining // Send final remaining time
            })
        });

        const data = await response.json();
        console.log("Server response on finish:", data);

        if (response.ok && data.redirect_url) {
            window.location.href = data.redirect_url;
        } else {
            showError(`Finishing action failed: ${data.message || 'An unknown error occurred.'}`);
        }
    } catch (error) {
        console.error("Network or fetch error during finish action:", error);
        showError("A network error occurred. Please check your connection and try again.");
    }
}


// =================================================================
// ASOSIY FUNKSIYALAR: JAVOB, SAVOL, NAVIGATSIYA
// =================================================================

function restoreUserAnswer(questionData) {
    const format = questionData.question_format;
    
    if (format === 'single' || format === 'multiple') {
        const selectedOptionIds = questionData.user_selected_options || []; 
        
        document.querySelectorAll('.option-item').forEach(optionItem => {
            const optionId = parseInt(optionItem.dataset.optionId);
            const isSelected = selectedOptionIds.includes(optionId);
            updateOptionUI(optionItem, isSelected);
        });
    } else if (format === 'short_answer') {
        const shortAnswerInput = document.getElementById('short-answer-input');
        if (shortAnswerInput) {
            shortAnswerInput.value = questionData.user_short_answer || '';
        }
    }

    const currentQId = questionIds[currentQuestionIndex];
    if (currentQId !== undefined) {
        const isReviewed = questionData.is_marked_for_review;
        if (isReviewed) {
            reviewedQuestionIds.add(currentQId);
        } else {
            reviewedQuestionIds.delete(currentQId);
        }
        markReviewBtn?.classList.toggle('marked', isReviewed);
    }
}

function attachAnswerListeners(format) {
    const optionItems = document.querySelectorAll('.option-item');
    optionItems.forEach(item => {
        item.onclick = null; 

        item.onclick = () => {
            const input = item.querySelector('input');
            if (!input) return;

            let willBeSelected;

            if (format === 'single') {
                document.querySelectorAll('.option-item').forEach(opt => {
                    updateOptionUI(opt, false); 
                });
                willBeSelected = true;
            } else if (format === 'multiple') {
                willBeSelected = !item.classList.contains('selected');
            }

            updateOptionUI(item, willBeSelected);
            saveAnswer();
        };
    });
    
    const shortAnswerInput = document.getElementById('short-answer-input');
    if (shortAnswerInput) {
        shortAnswerInput.onchange = null;
        shortAnswerInput.onchange = () => saveAnswer();
    }
}

async function saveAnswer(isNavigating = false) {
    const questionId = questionIds[currentQuestionIndex];
    if (questionId === undefined) return Promise.resolve(null);
    
    const questionFormat = document.getElementById('question_format')?.value || 'single';

    let payload = {
        action: 'save_answer', 
        attempt_id: ATTEMPT_ID,
        section_attempt_id: currentSectionId,
        question_id: questionId,
        is_marked_for_review: reviewedQuestionIds.has(questionId)
    };
    
    if (questionFormat === 'single') {
        const selectedOptionItem = document.querySelector('.option-item.selected');
        payload.selected_option = selectedOptionItem ? parseInt(selectedOptionItem.dataset.optionId) : null; 
    } else if (questionFormat === 'multiple') {
        const selectedOptionItems = Array.from(document.querySelectorAll('.option-item.selected'));
        payload.selected_options = selectedOptionItems.map(item => parseInt(item.dataset.optionId)); 
    } else if (questionFormat === 'short_answer') {
        const shortAnswerInput = document.getElementById('short-answer-input');
        payload.short_answer_text = shortAnswerInput ? shortAnswerInput.value.trim() : ''; 
    }
    
    return fetch(EXAM_AJAX_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
        body: JSON.stringify(payload)
    }).then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            answeredQuestionIds = new Set(data.answered_question_ids);
            generateNavButtons();
        } else {
            console.error("Javobni saqlashda xato:", data.message);
            showError("Javob saqlanmadi. Qayta urinib ko'ring.");
        }
        return data;
    })
    .catch(error => {
        console.error("Javobni saqlashda xato:", error);
        showError("Tarmoq xatosi. Javob local saqlanmoqda.");
        return { status: 'error', message: error.message };
    });
}

/**
 * 🔥 O'ZGARTIRILDI: Sarlavhani Mavzu Testi uchun moslashtirish
 */
async function loadQuestion(questionId, data = null) {
    if (!data && typeof fetchQuestionData === 'function') {
        const result = await fetchQuestionData(questionId);
        if (result.status === 'success') {
            data = result.question_data;
        }
    } 
    
    if (!data) {
        console.error("Savol ma'lumotlari topilmadi.");
        showError("Savolni yuklashda muammo yuz berdi. Qayta urinib ko'ring.");
        return;
    }

    const qIndex = questionIds.indexOf(questionId);
    if (qIndex === -1) return;
    currentQuestionIndex = qIndex;

    // UI elementlarini yangilash
    questionNumberEl.textContent = `${currentQuestionIndex + 1}`;
    
    // 🔥 MAVZU TESTI/SAT SARLAVHASINI MOSLASH
    if (typeof IS_SUBJECT_EXAM !== 'undefined' && IS_SUBJECT_EXAM) {
        // Mavzu testi bo'lsa, faqat imtihonning umumiy nomini ko'rsatish
        // data.exam_title serverdan keladi deb hisoblanadi
        questionNumberHeaderEl.textContent = data.exam_title || "Mavzu Imtihoni";
    } else {
        // To'liq SAT bo'lsa (Mavzu testi bo'lmasa), bo'lim nomini ko'rsatish
        const sectionData = SECTION_ATTEMPTS_DATA[currentSectionId] || { section_type: 'math_no_calc', module_number: 1 };
        
        let sectionTitle = 'Unknown Section';
        if (sectionData.section_type.startsWith('math')) {
            sectionTitle = `Math (Module ${sectionData.module_number})`;
        } else if (sectionData.section_type.startsWith('read_write')) {
            sectionTitle = `Reading & Writing (Module ${sectionData.module_number})`;
        }
        
        questionNumberHeaderEl.textContent = `${sectionTitle}`;
    }

    navModalBtn.querySelector('span').textContent = `Question ${currentQuestionIndex + 1} of ${questionIds.length}`;
    
    questionTextEl.innerHTML = data.question_text || "Savol matni mavjud emas.";
    answerOptionsContainer.innerHTML = data.options_html;
    document.getElementById('question_format').value = data.question_format || '';
    
    if (data.question_image_url && questionImageEl && questionImageContainer) {
        questionImageEl.src = data.question_image_url;
        questionImageContainer.style.display = 'block';
    } else if (questionImageContainer) {
        questionImageContainer.style.display = 'none';
    }
    
    cleanOptionText(answerOptionsContainer); 
    restoreUserAnswer(data);
    attachAnswerListeners(data.question_format);
    
    // MathJax: Faqat o'zgargan elementlarni render qilish (optimizatsiya)
    if (window.MathJax) {
        MathJax.typesetPromise([questionTextEl, answerOptionsContainer]).catch(err => console.warn("MathJax render xatosi:", err));
    }
    
    generateNavButtons();
    updateNavigationButtons();
}

// Navigatsiya tugmalarini generatsiya qilish
function generateNavButtons() {
    const targetContainer = navGrid; 
    if (!targetContainer) return;

    targetContainer.innerHTML = '';
    
    questionIds.forEach((id, index) => {
        const button = document.createElement('button');
        button.classList.add('nav-button', 'text-center', 'py-1', 'rounded', 'font-semibold', 'border', 'shadow-sm');
        button.dataset.index = index;
        button.textContent = index + 1;
        button.setAttribute('aria-label', `Savol ${index + 1} ga o'tish`);

        const isAnswered = answeredQuestionIds.has(id);
        const isReviewed = reviewedQuestionIds.has(id);
        const isActive = index === currentQuestionIndex;

        // Stil berish
        if (isActive) {
            button.classList.add('bg-blue-600', 'text-white', 'ring-2', 'ring-offset-2', 'ring-blue-500');
        } else if (isReviewed) {
            button.classList.add('bg-yellow-500', 'text-gray-800');
        } else if (isAnswered) {
            button.classList.add('bg-green-500', 'text-white');
        } else {
            button.classList.add('bg-gray-200', 'text-gray-800', 'hover:bg-gray-300'); 
        }

        button.addEventListener('click', () => {
            closeModal('question-nav-modal'); 
            
            saveAnswer(true).then(() => {
                loadQuestion(id);
            });
        });
        targetContainer.appendChild(button);
    });
}

async function loadInitialData(sectionAttemptId = currentSectionId) {
    if (!sectionAttemptId) {
        console.error("Section ID yuklanmadi.");
        return; 
    }
    
    try {
        const response = await fetch(EXAM_AJAX_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
            body: JSON.stringify({
                action: 'get_section_data', 
                attempt_id: ATTEMPT_ID,
                section_attempt_id: sectionAttemptId,
            })
        });
        const data = await response.json();
        console.log("Serverdan olingan ma'lumotlar:", data);

        if (data.status === 'success') {
            questionIds = data.question_ids || [];
            answeredQuestionIds = new Set(data.answered_question_ids || []);
            reviewedQuestionIds = new Set(data.marked_for_review || []); 
            // timeRemaining serverdan kelishi kerak, yoki bu yerda o'rnatilishi kerak
            timeRemaining = data.time_remaining !== undefined ? data.time_remaining : 2100;
            
            const initialQuestionData = data.initial_question_data;
            const initialQuestionId = data.initial_question_id;

            if (questionIds.length > 0 && initialQuestionId) {
                currentQuestionIndex = questionIds.indexOf(initialQuestionId) > -1 ? questionIds.indexOf(initialQuestionId) : 0;
                // initialQuestionData ichida ham exam_title bo'lishi kerak
                initialQuestionData.exam_title = data.exam_title; 
                await loadQuestion(questionIds[currentQuestionIndex], initialQuestionData);
                startTimer(); // Faqat bir marta ishga tushirish
            } else {
                questionTextEl.innerHTML = "<p>Ushbu bo'limda savollar mavjud emas.</p>";
            }
            generateNavButtons();
            updateNavigationButtons();
            saveToLocalStorage();
        } else {
            console.error("Initial data yuklanishida xato:", data.message);
            showError(`Bo'lim yuklashda xato: ${data.message || 'Qayta urinib koring.'}`);
        }
    } catch (error) {
        console.error("Initial data yuklanishida xato:", error);
        showError("Tarmoq xatosi. Internet aloqangizni tekshiring.");
    }
}

// =================================================================
// MODALLARNI BOSHQARISH (KALKULYATOR, FORMULA) - DESMOS LAZY-LOAD
// =================================================================

let desmosCalculator;

async function initDesmosCalculator() {
    if (desmosLoaded) {
        if (desmosCalculator) return;
    } else {
        try {
            await new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = 'https://www.desmos.com/api/v1.11/calculator.js?apiKey=b9fd3844def64e0ca90a786a646dd712';
                script.onload = () => {
                    desmosLoaded = true;
                    resolve();
                };
                script.onerror = reject;
                document.head.appendChild(script);
            });
        } catch (error) {
            console.error("Desmos yuklashda xato:", error);
            showError("Kalkulyator yuklanmadi. Brauzerni yangilang.");
            return;
        }
    }

    const elt = document.getElementById('desmos-calculator');
    if (elt && window.Desmos) {
        desmosCalculator = Desmos.GraphingCalculator(elt, {
            keypad: true, 
            expressionsCollapsed: true, 
            settingsMenu: false, 
            border: false 
        });
    }
}


// =================================================================
// GLOBAL HODISALARNI BIRIKTIRISH
// =================================================================

document.addEventListener('DOMContentLoaded', () => {
    // LocalStorage dan tiklash
    loadFromLocalStorage();

    // NEXT tugmasi bosilganda
    nextBtn?.addEventListener('click', () => {
        const action = nextBtn.dataset.action;
        if (action === 'finish_exam') {
            openModal('confirm-exit-modal'); // Mavzu testi tugatilishi
        } else if (action === 'finish_section') {
            handleFinishAction('finish_section'); // SAT bo'limini tugatish
        } else {
            handleNextOrFinish(); // Keyingi savolga o'tish
        }
    });

    // PREV tugmasi bosilganda
    prevBtn?.addEventListener('click', () => {
        saveAnswer(true).then(() => { 
            let prevIndex = currentQuestionIndex - 1;
            if (prevIndex >= 0) {
                loadQuestion(questionIds[prevIndex]);
            }
        });
    });

    hideTimerBtn?.addEventListener('click', toggleTimerVisibility);

    calculatorBtn?.addEventListener('click', () => openModal('calculator-modal'));
    referenceBtn?.addEventListener('click', () => {
        // loadReferenceFormulas global funksiya mavjud deb hisoblanadi
        if (typeof window.loadReferenceFormulas === 'function') {
            window.loadReferenceFormulas(); 
        }
        openModal('reference-modal');
    });
    directionsBtn?.addEventListener('click', () => openModal('directions-modal'));
    
    navModalBtn?.addEventListener('click', () => {
        generateNavButtons(); 
        openModal('question-nav-modal');
    });

    exitExamBtn?.addEventListener('click', () => openModal('confirm-exit-modal')); 
    
    confirmFinishYesBtn?.addEventListener('click', () => {
        handleFinishAction('finish_exam'); 
    });

    document.querySelectorAll('.close-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const modalId = e.currentTarget.dataset.modal || e.currentTarget.closest('.modal, .center-modal, .nav-modal')?.id;
            if (modalId) {
                closeModal(modalId);
            }
        });
    });

    markReviewBtn?.addEventListener('click', () => {
        const currentQId = questionIds[currentQuestionIndex];
        if (currentQId === undefined) return;

        if (reviewedQuestionIds.has(currentQId)) {
            reviewedQuestionIds.delete(currentQId);
            markReviewBtn.classList.remove('marked');
        } else {
            reviewedQuestionIds.add(currentQId);
            markReviewBtn.classList.add('marked');
        }
        saveAnswer(); 
    });
    
    // Section tablarini faqat bu yerda biriktirish (SAT uchun)
    document.querySelectorAll('.section-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            const newSectionId = e.currentTarget.dataset.sectionId;
            if (newSectionId !== currentSectionId) {
                saveAnswer().then(() => {
                    syncTimer().then(() => {
                        const sectionData = SECTION_ATTEMPTS_DATA[newSectionId];
                        if (sectionData && sectionData.is_completed) {
                            showError("Bu bo'lim allaqachon yakunlangan. Qayta kirib bo'lmaydi.");
                            return; 
                        }

                        document.querySelectorAll('.section-tab').forEach(t => t.classList.remove('active'));
                        e.currentTarget.classList.add('active');

                        currentSectionId = newSectionId;
                        questionIds = []; 
                        
                        if (timerInterval) clearInterval(timerInterval);
                        timerInterval = null;
                        timeRemaining = 2100; // Yangi bo'lim uchun (yoki serverdan olingan vaqt)
                        saveToLocalStorage();
                        loadInitialData(currentSectionId);
                    });
                });
            }
        });
    });

    loadInitialData(); // Dastlabki yuklash
});