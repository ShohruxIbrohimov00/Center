
const timerElement = document.getElementById('timer');
const hideTimerBtn = document.getElementById('hide-timer-btn');
const calculatorBtn = document.getElementById('calculator-btn');
const referenceBtn = document.getElementById('reference-btn');
const directionsBtn = document.getElementById('directions-btn');
const dictionaryBtn = document.getElementById('dictionary-btn'); 
const exitExamBtn = document.getElementById('exit-btn');
const confirmFinishModal = document.getElementById('confirm-exit-modal');
const confirmFinishYesBtn = document.getElementById('final-finish-btn');
const flashcardsContainer = document.getElementById('flashcards-container'); 
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
    localStorage.setItem(STORAGE_KEYS.TIME_REMAINING, window.timeRemaining.toString());
    localStorage.setItem(STORAGE_KEYS.CURRENT_SECTION, window.currentSectionId);
    localStorage.setItem(STORAGE_KEYS.LAST_SYNC, Date.now().toString());
}

function loadFromLocalStorage() {
    const savedTime = localStorage.getItem(STORAGE_KEYS.TIME_REMAINING);
    const savedSection = localStorage.getItem(STORAGE_KEYS.CURRENT_SECTION);
    if (savedTime && !isNaN(parseInt(savedTime))) {
        // timeRemaining - bu yerda globalda aniqlangan bo'lishi shart
        window.timeRemaining = parseInt(savedTime); 
    }
    if (savedSection && window.SECTION_ATTEMPTS_DATA[savedSection]) {
        // currentSectionId - bu yerda globalda aniqlangan bo'lishi shart
        window.currentSectionId = savedSection; 
    }
    lastSyncTime = parseInt(localStorage.getItem(STORAGE_KEYS.LAST_SYNC) || '0');
}

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
            // Checkmark SVG
            customElement.innerHTML = '<svg class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20"><path d="M0 11l2-2 5 5L18 3l2 2L7 18z"/></svg>';
        } else {
            customElement.classList.remove('bg-blue-600', 'border-blue-600');
            customElement.classList.add('border-gray-400');
            customElement.innerHTML = '';
        }
    }
}

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

function startTimer() {
    if (timerInterval) clearInterval(timerInterval);
    if (syncTimerInterval) clearInterval(syncTimerInterval);

    if (timerElement && window.timeRemaining !== undefined && window.timeRemaining >= 0) {
        timerElement.textContent = formatTime(window.timeRemaining);
        
        timerInterval = setInterval(async () => {
            if (window.timeRemaining <= 0) {
                clearInterval(timerInterval);
                timerElement.textContent = "00:00";
                // Mavzu testi bo'lsa darhol yakunlash
                const action = (typeof IS_SUBJECT_EXAM !== 'undefined' && IS_SUBJECT_EXAM) ? 'finish_exam' : 'finish_section';
                handleFinishAction(action); 
            } else {
                window.timeRemaining--;
                timerElement.textContent = formatTime(window.timeRemaining);
                saveToLocalStorage(); // Har soniyada local saqlash

                // Tarmoq onlayn bo'lsa, har 30 soniyada sinxronlash (debounce)
                if (navigator.onLine && Date.now() - lastSyncTime > 30000) {
                    await syncTimer();
                    lastSyncTime = Date.now();
                }
            }
        }, 1000);
    } else {
        console.error("Timer ishga tushmadi: timeRemaining aniqlanmadi yoki noto‘g‘ri", window.timeRemaining);
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
                section_attempt_id: window.currentSectionId,
                time_remaining: window.timeRemaining,
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


function updateNavigationButtons() {
    prevBtn.disabled = (currentQuestionIndex === 0);

    const totalQuestions = questionIds.length;
    const isLastQuestion = currentQuestionIndex === totalQuestions - 1;

    // NEXT tugmasini yangilash
    if (isLastQuestion) {
        // Mavzu Testi bo'lsa (bitta bo'lim = butun imtihon)
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
        
        // Agar finish_exam bo'lsa, modalni ochish
        if (action === 'finish_exam') {
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
    
    closeModal('confirm-exit-modal'); // Yakunlash modalini yopish

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
                section_attempt_id: window.currentSectionId,
                time_remaining: window.timeRemaining // Send final remaining time
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
    
    // 🔥 Tinglovchilarni ikki marta biriktirmaslik uchun avvalgisini o'chiramiz
    optionItems.forEach(item => {
        item.onclick = null; 

        item.onclick = () => {
            const input = item.querySelector('input');
            if (!input) return;

            let willBeSelected;

            if (format === 'single') {
                // Single choice: Boshqa variantlarni tanlanmagan holatga qaytarish
                document.querySelectorAll('.option-item').forEach(opt => {
                    if (opt !== item) {
                        updateOptionUI(opt, false); 
                    }
                });
                
                // Tanlangan variantni belgilash. Agar u allaqachon tanlangan bo'lsa ham, yana tanlash kerak.
                willBeSelected = true;
                
            } else if (format === 'multiple') {
                // Multiple choice: Tanlanmagan bo'lsa -> Tanlash, Tanlangan bo'lsa -> O'chirish
                willBeSelected = !item.classList.contains('selected');
            }

            // UI ni yangilash va javobni saqlash
            updateOptionUI(item, willBeSelected);
            saveAnswer();
        };
    });
    
    // Short Answer uchun tinglovchi
    const shortAnswerInput = document.getElementById('short-answer-input');
    if (shortAnswerInput) {
        // Har doim avvalgi tinglovchini o'chirish kerak, chunki savollar qayta yuklanadi
        shortAnswerInput.onchange = null;
        shortAnswerInput.onchange = () => saveAnswer();
    }
}

async function saveAnswer(isNavigating = false) {
    console.log("Saving answer for section_attempt_id:", window.currentSectionId); 
    const questionId = questionIds[currentQuestionIndex];
    if (questionId === undefined) return Promise.resolve(null);
    
    const questionFormat = document.getElementById('question_format')?.value || 'single';

    let payload = {
        action: 'save_answer', 
        attempt_id: ATTEMPT_ID,
        section_attempt_id: window.currentSectionId,
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
        
    // Javob belgilanmagan bo'lsa, 'answered' ro'yxatidan o'chirishni ta'minlaymiz
    const isAnsweredNow = payload.selected_option || (payload.selected_options && payload.selected_options.length > 0) || payload.short_answer_text;

    return fetch(EXAM_AJAX_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
        body: JSON.stringify(payload)
    }).then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Serverdan kelgan yangilangan ro'yxatni olish kutiladi (yoki biz lokal yangilaymiz)
            if (data.answered_question_ids) {
                answeredQuestionIds = new Set(data.answered_question_ids);
            } else {
                // Agar server ro'yxatni yubormasa, lokal yangilaymiz
                if (isAnsweredNow) {
                    answeredQuestionIds.add(questionId);
                } else {
                    answeredQuestionIds.delete(questionId);
                }
            }
            generateNavButtons();
        } else {
            console.error("Javobni saqlashda xato:", data.message);
            showError("Javob saqlanmadi. Qayta urinib ko'ring.");
        }
        return data;
    })
    .catch(error => {
        console.error("Javobni saqlashda tarmoq xatosi:", error);
        showError("Tarmoq xatosi. Javob saqlanmadi.");
        return { status: 'error', message: error.message };
    });
}


async function loadQuestion(questionId, data = null) {
    console.log("loadQuestion chaqirildi. Yuklanayotgan ID:", questionId); 
    console.log("Mavzu testi holati:", (typeof IS_SUBJECT_EXAM !== 'undefined' && IS_SUBJECT_EXAM));     
    if (!data && typeof window.fetchQuestionData === 'function') { 
        // window.fetchQuestionData - bu HTML ichidagi script blokidan keladi
        const result = await window.fetchQuestionData(questionId);
        if (result.status === 'success') {
            data = result.question_data;
        }
    } 
    
    if (!data) {
        console.error("Savol ma'lumotlari topilmadi.");
        return;
    }

    const qIndex = questionIds.indexOf(questionId);
    if (qIndex === -1) return;
    currentQuestionIndex = qIndex;

    // UI elementlarini yangilash
    questionNumberEl.textContent = `${currentQuestionIndex + 1}`;
    
    const isSubject = (typeof IS_SUBJECT_EXAM !== 'undefined' && IS_SUBJECT_EXAM);

    if (isSubject) {
        // Mavzu testi bo'lsa, faqat imtihonning umumiy nomini ko'rsatish
        // data.exam_title serverdan kelishi kerak
        questionNumberHeaderEl.textContent = data.exam_title || "Mavzu Imtihoni";
    } else {
        // To'liq SAT bo'lsa, bo'lim nomini ko'rsatish
        const sectionData = window.SECTION_ATTEMPTS_DATA[window.currentSectionId] || { section_type: 'math_no_calc', module_number: 1 };
        
        let sectionTitle = 'Unknown Section';
        if (sectionData.section_type.startsWith('math')) {
            sectionTitle = `Math (Module ${sectionData.module_number})`;
        } else if (sectionData.section_type.startsWith('read_write')) {
            sectionTitle = `Reading & Writing (Module ${sectionData.module_number})`;
        }
        
        questionNumberHeaderEl.textContent = `${sectionTitle}`;
    }

    // Lug'at tugmasini boshqarish
    if (dictionaryBtn) {
        dictionaryBtn.style.display = isSubject ? 'flex' : 'none'; 
    }
    
    navModalBtn.querySelector('span').textContent = `Question ${currentQuestionIndex + 1} of ${questionIds.length}`;
    
    questionTextEl.innerHTML = data.question_text || "Savol matni mavjud emas.";
    answerOptionsContainer.innerHTML = data.options_html;
    
    // Savol formati ma'lumotini saqlash
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

async function loadInitialData(sectionAttemptId = window.currentSectionId) {
    console.log("loadInitialData chaqirildi. Bo'lim ID:", sectionAttemptId); // 🔥 DEBUG QATORI
    
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
        console.log("Serverdan olingan bo'lim ma'lumotlari:", data);

        if (data.status === 'success') {
            
            const questions = data.questions || [];
            
            // Savol IDlarini ajratib olish
            questionIds = questions.map(q => q.id);
            
            // Answered va Reviewed IDlarni tiklash
            answeredQuestionIds = new Set(questions.filter(q => q.is_answered).map(q => q.id));
            reviewedQuestionIds = new Set(questions.filter(q => q.is_marked).map(q => q.id));
            
            if (questionIds.length > 0) {
                
                currentQuestionIndex = 0; 
                console.log("loadInitialData: Birinchi savol IDsi:", questionIds[currentQuestionIndex]); // 🔥 DEBUG QATORI

                await loadQuestion(questionIds[currentQuestionIndex]);
                
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
        console.error("Initial data yuklanishida tarmoq xatosi:", error);
        showError("Tarmoq xatosi. Internet aloqangizni tekshiring.");
    }
}

async function loadFlashcardsForCurrentQuestion() {
    const questionId = questionIds[currentQuestionIndex];
    if (!questionId || !flashcardsContainer) return;
    
    flashcardsContainer.innerHTML = '<div class="text-center p-4">Lug\'atlar yuklanmoqda...</div>';

    try {
        const response = await fetch(EXAM_AJAX_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
            body: JSON.stringify({
                action: 'get_flashcards', 
                attempt_id: ATTEMPT_ID,
                question_id: questionId,
            })
        });

        const data = await response.json();

        if (data.status === 'success' && data.flashcards && data.flashcards.length > 0) {
            flashcardsContainer.innerHTML = generateFlashcardsHTML(data.flashcards);
            
            if (window.MathJax) {
                MathJax.typesetPromise([flashcardsContainer]).catch(err => console.warn("Flashcard MathJax xatosi:", err));
            }
            
        } else {
            flashcardsContainer.innerHTML = '<div class="text-center p-4 text-gray-500">Bu savolga tegishli lug\'atlar (Flashcardlar) topilmadi.</div>';
        }
    } catch (error) {
        console.error("Flashcard yuklashda xato:", error);
        flashcardsContainer.innerHTML = '<div class="text-center p-4 text-red-500">Tarmoq xatosi yoki serverga ulanishda muammo.</div>';
    }
}

function generateFlashcardsHTML(flashcards) {
    let html = '<div class="grid gap-4">';
    flashcards.forEach(card => {
        html += `
            <div class="border rounded-lg shadow-md p-4 bg-white">
                <h4 class="font-bold text-lg mb-1 text-blue-700">${card.term || 'Atama Nomi'}</h4>
                <p class="text-gray-700">${card.definition || 'Ta’rifi'}</p>
            </div>
        `;
    });
    html += '</div>';
    return html;
}


let desmosCalculator;

// Global funksiya sifatida window.initDesmosCalculator deb e'lon qilish
window.initDesmosCalculator = async function() {
    if (desmosLoaded) {
        if (desmosCalculator) return;
    } else {
        try {
            await new Promise((resolve, reject) => {
                const script = document.createElement('script');
                // Desmos uchun ruxsatnomangizni ishlatish
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

document.addEventListener('DOMContentLoaded', () => {
    // LocalStorage dan tiklash
    loadFromLocalStorage();
    
    // 🔥 Flashcards uchun modalni qo'shamiz (Agar HTMLda bo'lmasa)
    if (!document.getElementById('flashcards-modal')) {
        // Agar sizning HTMLingizda bo'lmasa, uni qo'shish kerak. Hozircha bu yerni o'tkazib yuboramiz.
    }


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
    
    // 🔥 YANGI O'ZGARTIRISH: Lug'at (Flashcard) tugmasi
    dictionaryBtn?.addEventListener('click', () => {
        // Faqat Mavzu Testi bo'lsa ko'rsatish
        if (typeof IS_SUBJECT_EXAM !== 'undefined' && IS_SUBJECT_EXAM) {
            loadFlashcardsForCurrentQuestion(); 
            openModal('flashcards-modal'); // 🔥 Modal ID to'g'ri bo'lishi kerak
        } else {
            showError("Lug'at funksiyasi faqat mavzu testida mavjud."); 
        }
    });

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
            if (newSectionId !== window.currentSectionId) {
                saveAnswer().then(() => {
                    syncTimer().then(() => {
                        const sectionData = window.SECTION_ATTEMPTS_DATA[newSectionId];
                        if (sectionData && sectionData.is_completed) {
                            showError("Bu bo'lim allaqachon yakunlangan. Qayta kirib bo'lmaydi.");
                            return; 
                        }

                        document.querySelectorAll('.section-tab').forEach(t => t.classList.remove('active'));
                        e.currentTarget.classList.add('active');

                        window.currentSectionId = newSectionId;
                        questionIds = []; 
                        
                        if (timerInterval) clearInterval(timerInterval);
                        timerInterval = null;
                        // Yangi bo'lim uchun vaqtni tiklash kerak. 
                        // Ammo loadInitialData() ham serverdan vaqtni yangilashi mumkin.
                        // window.timeRemaining = sectionData.time_limit_seconds || 2100; 
                        
                        saveToLocalStorage();
                        loadInitialData(window.currentSectionId);
                    });
                });
            }
        });
    });

    loadInitialData(); // Dastlabki yuklash
});