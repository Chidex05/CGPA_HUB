// ==========================================================================
// TARGET CGPA GOAL PLANNER CALCULATION ENGINE
// ==========================================================================

const menuToggle= document.getElementById("menu-toggle");
const mainNav= document.getElementById("main-nav");
if (menuToggle && mainNav){
    menuToggle.addEventListener("click",function()
{const isOpen= mainNav.classList.toggle("active");
    menuToggle.innerHTML= isOpen ? '<i class= "fa-solid fa-xmark"></i>':
     '<i class= "fa-solid fa-bars"></i>';
     menuToggle.setAttribute("aria-expanded", isOpen);
     menuToggle.setAttribute("aria-label", isOpen ? "close navigation menu": "Open navigation menu");

}); 
}

document.addEventListener("DOMContentLoaded", function() { 
    const calcGoalBtn = document.getElementById("calculate-goal-btn"); 
    if (!calcGoalBtn) return; 

    // Keep references to the Elements, not their initial empty values
    const currentCGPAInput = document.getElementById("current-cgpa"); 
    const completedUnitsInput = document.getElementById("completed-units"); 
    const targetCGPAInput = document.getElementById("target-cgpa-input"); 
    const nextSemesterUnitsInput = document.getElementById("next-units-input"); 
    
    const resultBox = document.getElementById("goal-result-box"); 
    const gpaDisplay = document.getElementById("required-gpa-display"); 
    const feedbackMsg = document.getElementById("goal-feedback-msg"); 
    const gradingSystemSelect = document.getElementById("grading-system");
    let gradingSystem = localStorage.getItem("gradingSystem") || "5";
    if (gradingSystemSelect) {
        gradingSystemSelect.value = ["4", "5"].includes(gradingSystem) ? gradingSystem : "5";
        gradingSystem = gradingSystemSelect.value;
        currentCGPAInput.max = gradingSystem;
        targetCGPAInput.max = gradingSystem;
        targetCGPAInput.placeholder = gradingSystem === "4" ? "e.g. 3.50" : "e.g. 4.50";
        gradingSystemSelect.addEventListener("change", () => {
            gradingSystem = gradingSystemSelect.value;
            localStorage.setItem("gradingSystem", gradingSystem);
            const maximum = Number(gradingSystem);
            pointsMap = gradingSystem === "4"
                ? { "A": 4, "B": 3, "C": 2, "D": 1, "E": 0, "F": 0 }
                : { "A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "F": 0 };
            currentCGPAInput.max = String(maximum);
            targetCGPAInput.max = String(maximum);
            targetCGPAInput.placeholder = gradingSystem === "4" ? "e.g. 3.50" : "e.g. 4.50";
            loadAcademicRecord();
        });
    }

    let pointsMap = gradingSystem === "4"
        ? { "A": 4, "B": 3, "C": 2, "D": 1, "E": 0, "F": 0 }
        : { "A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "F": 0 };

    function getAcademicrecord() { 
        const savedCourses = JSON.parse(localStorage.getItem("cgpaCourses")) || []; 
        let currentUnits = 0; 
        let currentPoints = 0; 
        
        savedCourses.forEach(course => { 
            const unit = Number(course.unit); 
            const grade = String(course.grade || "").trim().toUpperCase(); 
            if (Number.isInteger(unit) && unit > 0 && Object.hasOwn(pointsMap, grade)) { 
                currentUnits += unit; 
                currentPoints += unit * pointsMap[grade]; 
            } 
        }); 
        const currentCGPA = currentUnits > 0 ? currentPoints / currentUnits : 0; 
        return { currentUnits, currentCGPA }; 
    } 

    function loadAcademicRecord() { 
        const record = getAcademicrecord(); 
        currentCGPAInput.value = record.currentUnits > 0 ? record.currentCGPA.toFixed(2) : ""; 
        completedUnitsInput.value = record.currentUnits || ""; 
    } 
    
    loadAcademicRecord(); 

    calcGoalBtn.addEventListener("click", () => { 
        const record = getAcademicrecord(); 
        const currentCGPA = record.currentCGPA; 
        const completedUnits = record.currentUnits; 
        
        // Grab the live numeric values upon click
        const targetCGPA = Number(targetCGPAInput.value); 
        const nextSemesterUnits = Number(nextSemesterUnitsInput.value); 

        // VALIDATION
        if (completedUnits <= 0) { // Fixed variable name
            alert("Please calculate your current CGPA first by adding your courses and grades."); 
            return; 
        } 
        const maximum = gradingSystem === "4" ? 4 : 5;
        if (targetCGPAInput.value === "" || !Number.isFinite(targetCGPA) || targetCGPA <= 0 || targetCGPA > maximum) { 
            alert(`Please enter a valid target CGPA between 0.00 and ${maximum.toFixed(2)}.`);
            return; 
        } 
        if (nextSemesterUnitsInput.value === "" || !Number.isInteger(nextSemesterUnits) || nextSemesterUnits <= 0) { 
            alert("Please enter a valid number of units for the next semester."); 
            return; 
        } 

        // Math.max (Capital M) and fixed missing parenthesis layout
        const requiredGPA = ((targetCGPA * (completedUnits + nextSemesterUnits)) - (currentCGPA * completedUnits)) / nextSemesterUnits; 

        // Display result 
        resultBox.style.display = "block"; 
        gpaDisplay.textContent = Math.max(0, requiredGPA).toFixed(2); 

        // Corrected logical feedback
        if (requiredGPA <= currentCGPA) {
            gpaDisplay.style.color = "#10b981"; // Green
            feedbackMsg.textContent = "You are already on track or above this target! Maintain your performance.";
        } else if (requiredGPA > maximum) { 
            gpaDisplay.style.color = "#ef4444"; // Red 
            feedbackMsg.textContent = "Mathematically impossible next semester. Lower your target or add more units."; 
        } else if (requiredGPA > (gradingSystem === "4" ? 3.5 : 4.5)) { 
            gpaDisplay.style.color = "#f97316"; // Orange 
            feedbackMsg.textContent = "Extremely high target! You will need straight A's next semester."; 
        } else { 
            gpaDisplay.style.color = "#10b981"; // Green 
            feedbackMsg.textContent = `Achievable! Target an average of ${requiredGPA.toFixed(2)} next term to lock this in.`; 
        } 
    }); 
});