// ==========================================================================
// FIXED DASHBOARD LOGIC ENGINE
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

function runDashboardEngine() {
    // 1. Pull the data array securely out of local storage
    const storedData = localStorage.getItem("cgpaCourses");
    const savedCourses = storedData ? JSON.parse(storedData) : [];
    
    // Safety check: Exit cleanly if the DOM nodes are missing from the current page view layout
    if (!document.getElementById("dash-cgpa")) return;

    let totalUnits = 0;
    let totalEarnedPoints = 0;
    const totalCoursesCount = savedCourses.length;

    // Grade Weight Evaluation Schema
    const pointsMap = { "A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "F": 0 };

    // 2. Compute aggregate values
    savedCourses.forEach(course => {
        const unit = Number(course.unit) || 0;
        const gradeLetter = (course.grade || "").trim().toUpperCase();
        const points = pointsMap[gradeLetter] !== undefined ? pointsMap[gradeLetter] : 0;
        
        totalUnits += unit;
        totalEarnedPoints += (unit * points);
    });

    // 3. Calculate final global dynamic average
    const computedCGPA = totalUnits > 0 ? (totalEarnedPoints / totalUnits) : 0;

    // 4. Update the metric text values on the page layout cards
    document.getElementById("dash-cgpa").textContent = computedCGPA.toFixed(2);
    document.getElementById("dash-units").textContent = totalUnits;

    // Determine Degree Honors Ranking Tier Classifications
    let tierText = "Pass";
    if (computedCGPA >= 4.50) tierText = "First Class";
    else if (computedCGPA >= 3.50) tierText = "2nd Class Upper";
    else if (computedCGPA >= 2.40) tierText = "2nd Class Lower";
    else if (computedCGPA >= 1.50) tierText = "Third Class";
    if (totalCoursesCount === 0) tierText = "No Data Yet";

    document.getElementById("dash-standing").textContent = tierText;

    // 5. Update the advice panel message based on the user's performance status
    const messageNode = document.getElementById("dash-insight-msg");
    if (messageNode) {
        if (totalCoursesCount === 0) {
            messageNode.innerHTML = `<i class="fa-solid fa-lightbulb text-yellow"></i> Welcome! Your dashboard is active. Head over to the calculator page to add modules and compute your first term scores.`;
        } else if (computedCGPA >= 4.50) {
            messageNode.innerHTML = `<i class="fa-solid fa-circle-check" style="color: #10b981;"></i> Excellent academic standing! Maintain your momentum to graduate with a <strong>First Class</strong> distinction.`;
        } else {
            messageNode.innerHTML = `<i class="fa-solid fa-arrow-trend-up" style="color: #3b82f6;"></i> Profile tracking updated. Your overall average is currently sitting at a <strong>${computedCGPA.toFixed(2)}</strong> index.`;
        }
    }
}

// Ensure the execution engine runs as soon as the DOM tree finishes loading
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", runDashboardEngine);
} else {
    runDashboardEngine();
}
