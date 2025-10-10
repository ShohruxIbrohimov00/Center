/*
 * ==========================================================
 * SAT Reference Formulas
 * ==========================================================
 * Adapted to the official Digital SAT reference sheet, with SVG diagrams
 */

/**
 * Database of formulas
 * Each formula includes title, formula (if applicable), description, and svg fields
 */
const satFormulas = {
  "Area and Circumference": [
    {
      "title": "Area of a Circle",
      "formula": "$$A = \\pi r^2$$",
      "description": "The radius of the circle is <span class='math'>$r$</span>.",
      "svg": `
        <svg width="80" height="80" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" stroke="#272626" stroke-width="2" fill="none"/>
          <line x1="50" y1="50" x2="90" y2="50" stroke="#272626" stroke-width="2"/>
          <text x="70" y="45" font-size="12" fill="#272626">r</text>
        </svg>
      `
    },
    {
      "title": "Circumference of a Circle",
      "formula": "$$C = 2\\pi r$$",
      "description": "The radius of the circle is <span class='math'>$r$</span>.",
      "svg": `
        <svg width="80" height="80" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" stroke="#272626" stroke-width="2" fill="none"/>
          <line x1="50" y1="50" x2="90" y2="50" stroke="#272626" stroke-width="2"/>
          <text x="70" y="45" font-size="12" fill="#272626">r</text>
        </svg>
      `
    },
    {
      "title": "Area of a Rectangle",
      "formula": "$$A = lw$$",
      "description": "The length is <span class='math'>$l$</span> and the width is <span class='math'>$w$</span>.",
      "svg": `
        <svg width="80" height="60" viewBox="0 0 100 75">
          <rect x="10" y="10" width="80" height="55" stroke="#272626" stroke-width="2" fill="none"/>
          <text x="45" y="5" font-size="12" fill="#272626">l</text>
          <text x="95" y="40" font-size="12" fill="#272626">w</text>
        </svg>
      `
    },
    {
      "title": "Area of a Triangle",
      "formula": "$$A = \\frac{1}{2}bh$$",
      "description": "The base is <span class='math'>$b$</span> and the height is <span class='math'>$h$</span>.",
      "svg": `
        <svg width="80" height="60" viewBox="0 0 100 75">
          <polygon points="10,65 90,65 50,10" stroke="#272626" stroke-width="2" fill="none"/>
          <line x1="50" y1="65" x2="50" y2="10" stroke="#272626" stroke-width="2" stroke-dasharray="2,2"/>
          <text x="45" y="70" font-size="12" fill="#272626">b</text>
          <text x="55" y="40" font-size="12" fill="#272626">h</text>
        </svg>
      `
    },
    {
      "title": "Pythagorean Theorem",
      "formula": "$$a^2 + b^2 = c^2$$",
      "description": "In a right triangle, the legs are <span class='math'>$a$</span> and <span class='math'>$b$</span>, and the hypotenuse is <span class='math'>$c$</span>.",
      "svg": `
        <svg width="80" height="60" viewBox="0 0 100 75">
          <polygon points="10,65 90,65 10,10" stroke="#272626" stroke-width="2" fill="none"/>
          <text x="5" y="40" font-size="12" fill="#272626">a</text>
          <text x="45" y="70" font-size="12" fill="#272626">b</text>
          <text x="50" y="30" font-size="12" fill="#272626">c</text>
        </svg>
      `
    },
    {
      "title": "Central Angle of a Circle",
      "formula": "$$\\text{degree measure} = \\frac{s}{r}$$",
      "description": "The arc length is <span class='math'>$s$</span> and the radius is <span class='math'>$r$</span>, with the angle in degrees.",
      "svg": `
        <svg width="80" height="80" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" stroke="#272626" stroke-width="2" fill="none"/>
          <path d="M50,50 L90,50 A40,40 0 0,1 70,80" stroke="#272626" stroke-width="2" fill="none"/>
          <text x="70" y="45" font-size="12" fill="#272626">r</text>
          <text x="80" y="70" font-size="12" fill="#272626">s</text>
          <text x="55" y="65" font-size="12" fill="#272626">θ</text>
        </svg>
      `
    }
  ],
  "Special Right Triangles": [
    {
      "title": "30-60-90 Triangle",
      "formula": "$$\\text{Sides}: x, x\\sqrt{3}, 2x$$",
      "description": "In a 30-60-90 triangle, the side lengths are: short leg <span class='math'>$x$</span>, long leg <span class='math'>$x\\sqrt{3}$</span>, hypotenuse <span class='math'>$2x$</span>.",
      "svg": `
        <svg width="80" height="80" viewBox="0 0 100 100">
          <polygon points="10,90 90,90 10,10" stroke="#272626" stroke-width="2" fill="none"/>
          <text x="5" y="50" font-size="12" fill="#272626">x</text>
          <text x="50" y="95" font-size="12" fill="#272626">x√3</text>
          <text x="50" y="30" font-size="12" fill="#272626">2x</text>
          <text x="15" y="85" font-size="12" fill="#272626">30°</text>
          <text x="80" y="85" font-size="12" fill="#272626">60°</text>
        </svg>
      `
    },
    {
      "title": "45-45-90 Triangle",
      "formula": "$$\\text{Sides}: x, x, x\\sqrt{2}$$",
      "description": "In a 45-45-90 triangle, the side lengths are: legs <span class='math'>$x$</span>, hypotenuse <span class='math'>$x\\sqrt{2}$</span>.",
      "svg": `
        <svg width="80" height="80" viewBox="0 0 100 100">
          <polygon points="10,90 90,90 10,10" stroke="#272626" stroke-width="2" fill="none"/>
          <text x="5" y="50" font-size="12" fill="#272626">x</text>
          <text x="50" y="95" font-size="12" fill="#272626">x</text>
          <text x="50" y="30" font-size="12" fill="#272626">x√2</text>
          <text x="15" y="85" font-size="12" fill="#272626">45°</text>
          <text x="80" y="85" font-size="12" fill="#272626">45°</text>
        </svg>
      `
    }
  ],
  "Volume": [
    {
      "title": "Volume of a Rectangular Prism",
      "formula": "$$V = lwh$$",
      "description": "The length is <span class='math'>$l$</span>, the width is <span class='math'>$w$</span>, and the height is <span class='math'>$h$</span>.",
      "svg": `
        <svg width="80" height="80" viewBox="0 0 100 100">
          <path d="M20,80 L80,80 L90,50 L30,50 Z M30,50 L40,20 L100,20 L90,50 M20,80 L30,50 M80,80 L90,50 M40,20 L20,80" stroke="#272626" stroke-width="2" fill="none"/>
          <text x="50" y="85" font-size="12" fill="#272626">l</text>
          <text x="85" y="65" font-size="12" fill="#272626">w</text>
          <text x="15" y="50" font-size="12" fill="#272626">h</text>
        </svg>
      `
    },
    {
      "title": "Volume of a Cylinder",
      "formula": "$$V = \\pi r^2 h$$",
      "description": "The radius is <span class='math'>$r$</span> and the height is <span class='math'>$h$</span>.",
      "svg": `
        <svg width="80" height="80" viewBox="0 0 100 100">
          <ellipse cx="50" cy="20" rx="30" ry="10" stroke="#272626" stroke-width="2" fill="none"/>
          <ellipse cx="50" cy="80" rx="30" ry="10" stroke="#272626" stroke-width="2" fill="none"/>
          <path d="M20,20 L20,80 M80,20 L80,80" stroke="#272626" stroke-width="2" fill="none"/>
          <text x="55" y="50" font-size="12" fill="#272626">h</text>
          <text x="35" y="15" font-size="12" fill="#272626">r</text>
        </svg>
      `
    },
    {
      "title": "Volume of a Cone",
      "formula": "$$V = \\frac{1}{3}\\pi r^2 h$$",
      "description": "The radius is <span class='math'>$r$</span> and the height is <span class='math'>$h$</span>.",
      "svg": `
        <svg width="80" height="80" viewBox="0 0 100 100">
          <ellipse cx="50" cy="80" rx="30" ry="10" stroke="#272626" stroke-width="2" fill="none"/>
          <path d="M20,80 L50,20 L80,80" stroke="#272626" stroke-width="2" fill="none"/>
          <line x1="50" y1="80" x2="50" y2="20" stroke="#272626" stroke-width="2" stroke-dasharray="2,2"/>
          <text x="55" y="50" font-size="12" fill="#272626">h</text>
          <text x="35" y="85" font-size="12" fill="#272626">r</text>
        </svg>
      `
    },
    {
      "title": "Volume of a Sphere",
      "formula": "$$V = \\frac{4}{3}\\pi r^3$$",
      "description": "The radius is <span class='math'>$r$</span>.",
      "svg": `
        <svg width="80" height="80" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="30" stroke="#272626" stroke-width="2" fill="none"/>
          <line x1="50" y1="50" x2="80" y2="50" stroke="#272626" stroke-width="2"/>
          <text x="65" y="45" font-size="12" fill="#272626">r</text>
        </svg>
      `
    },
    {
      "title": "Volume of a Pyramid",
      "formula": "$$V = \\frac{1}{3}Bh$$",
      "description": "The base area is <span class='math'>$B$</span> and the height is <span class='math'>$h$</span>.",
      "svg": `
        <svg width="80" height="80" viewBox="0 0 100 100">
          <rect x="20" y="60" width="60" height="30" stroke="#272626" stroke-width="2" fill="none"/>
          <path d="M50,20 L20,60 M50,20 L80,60 M50,20 L50,60" stroke="#272626" stroke-width="2" fill="none"/>
          <text x="45" y="95" font-size="12" fill="#272626">B</text>
          <text x="55" y="40" font-size="12" fill="#272626">h</text>
        </svg>
      `
    }
  ]
};

/**
 * Renders formulas into HTML and calls MathJax for processing.
 * This function should be called by exam_mode.js when the 'Reference' button is clicked (i.e., when the modal is opened).
 */
function loadReferenceFormulas() {
    const formulaPanel = document.getElementById('formula-panel');
    if (!formulaPanel) {
        console.error("Error: 'formula-panel' element not found.");
        return;
    }

    // Paneldagi eski ma'lumotlarni tozalaymiz
    formulaPanel.innerHTML = ''; 

    // Kategoriyalar bo'yicha aylanib chiqamiz
    for (const categoryKey in satFormulas) {
        if (satFormulas.hasOwnProperty(categoryKey)) {
            const formulas = satFormulas[categoryKey];
            
            // Kategoriya sarlavhasini yaratamiz
            const titleElement = document.createElement('h3');
            titleElement.className = "text-lg font-bold mt-4 mb-2";
            titleElement.textContent = categoryKey.toUpperCase();
            formulaPanel.appendChild(titleElement);
            
            // Har bir formula uchun alohida element yaratamiz
            formulas.forEach(item => {
                // Asosiy konteyner (formula-item)
                const itemDiv = document.createElement('div');
                itemDiv.className = "formula-item p-3 bg-gray-100 rounded-md mb-2 flex items-start gap-4";
                
                // Matnlar uchun chap taraf
                const textContentDiv = document.createElement('div');
                textContentDiv.className = 'flex-1';
                
                let textHtml = `<strong>${item.title}</strong>`;
                if (item.formula) {
                    textHtml += `<div class="formula-latex">${item.formula}</div>`;
                }
                textHtml += `<p class="text-sm text-gray-600 mathjax">${item.description}</p>`;
                
                textContentDiv.innerHTML = textHtml;
                
                // Chizma (SVG) uchun o'ng taraf
                if (item.svg) {
                    const svgContainer = document.createElement('div');
                    svgContainer.className = 'formula-svg';
                    // SVG'ni matn sifatida emas, to'g'ridan-to'g'ri 'innerHTML' orqali shu kichik div'ga qo'shamiz
                    // Bu brauzerni uni to'g'ri chizishga majbur qiladi
                    svgContainer.innerHTML = item.svg.trim();
                    itemDiv.appendChild(textContentDiv);
                    itemDiv.appendChild(svgContainer);
                } else {
                    itemDiv.appendChild(textContentDiv);
                }
                
                // Yaratilgan to'liq elementni asosiy panelga qo'shamiz
                formulaPanel.appendChild(itemDiv);
            });
        }
    }

    // MathJax'ni qayta ishga tushiramiz
    if (window.MathJax) {
        MathJax.typesetPromise([formulaPanel]).catch(function (err) {
            console.error('MathJax rendering error:', err);
        });
    } else {
        console.warn("MathJax library not loaded. Formulas may not render correctly.");
    }
}

// Ensure availability in global scope
window.satFormulas = satFormulas;
window.loadReferenceFormulas = loadReferenceFormulas;