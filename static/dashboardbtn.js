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


const calcGoalBtn = document.getElementById("calculate-goal-btn");

if (calcGoalBtn) {
    calcGoalBtn.addEventListener("click", () => {
        const targetInput = document.getElementById("target-cgpa-input").value;
        const nextUnitsInput = document.getElementById("next-units-input").value;

        if (!targetInput || !nextUnitsInput) {
            alert("Please fill in both your graduation target and next semester's total units.");
            return;
        }

        const targetCGPA = parseFloat(targetInput);
        const nextSemesterUnits = parseInt(nextUnitsInput);

        if (targetCGPA > 5.0 || targetCGPA < 0) {
            alert("Please enter a valid target CGPA between 0.00 and 5.00.");
            return;
        }

        // Gather current stats directly from what's already saved in storage
        const savedCourses = JSON.parse(localStorage.getItem("gpaCourses")) || [];
        let currentUnits = 0;
        let currentPoints = 0;
        const pointsMap = { "A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "F": 0 };

        savedCourses.forEach(c => {
            const u = Number(c.unit) || 0;
            const p = pointsMap[(c.grade || "").trim().toUpperCase()] || 0;
            currentUnits += u;
            currentPoints += (u * p);
        });

        // ALGEBRA EQUATION: Target Quality Points = (Current Units + Next Units) * Target CGPA
        const totalFutureUnits = currentUnits + nextSemesterUnits;
        const totalTargetPoints = totalFutureUnits * targetCGPA;
        const requiredNextPoints = totalTargetPoints - currentPoints;
        
        // Target GPA = Required Points / Next Semester Units
        const requiredGPA = nextSemesterUnits > 0 ? (requiredNextPoints / nextSemesterUnits) : 0;

        // Display results dynamically
        const resultBox = document.getElementById("goal-result-box");
        const gpaDisplay = document.getElementById("required-gpa-display");
        const feedbackMsg = document.getElementById("goal-feedback-msg");

        gpaDisplay.textContent = requiredGPA <= 0 ? "0.00" : requiredGPA.toFixed(2);
        resultBox.style.display = "block";

        // Give tailored feedback based on the target difficulty metrics
        if (requiredGPA > 5.0) {
            gpaDisplay.style.color = "#ef4444"; // Red text alert
            feedbackMsg.innerHTML = `<span style="color: #ef4444;">⚠️ Mathematically impossible</span> this semester. Try lowering your target or increasing your total units timeline track.`;
        } else if (requiredGPA > 4.5) {
            gpaDisplay.style.color = "#f97316"; // Orange text alert
            feedbackMsg.textContent = "🔥 Extremely high target! You will need straight A's next semester.";
        } else if (requiredGPA <= 0) {
            gpaDisplay.style.color = "#10b981"; // Green text success
            feedbackMsg.textContent = "✨ You have already accumulated enough credit weight points to coast into this target!";
        } else {
            gpaDisplay.style.color = "#10b981"; // Green text success
            feedbackMsg.textContent = `🎯 Achievable! Target an average of ${requiredGPA.toFixed(2)} next term to lock this in.`;
        }
    });
}