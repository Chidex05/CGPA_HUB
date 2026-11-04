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



let courses = JSON.parse(localStorage.getItem("gpaCourses")) || [];
let editingIndex = null;

// Unified render function to accurately draw table data based on HTML headers
function renderCourses() {
    const courseList = document.getElementById("course-list");
    if (!courseList) return; // Safety exit if not on the calculator page
    courseList.innerHTML = ""; // Clear current rows

    if (courses.length > 0) {
        courses.forEach((course, index) => {
            const row = courseList.insertRow();
            row.innerHTML = `
            <td> ${index + 1} </td>
            <td> ${course.code} </td>
            <td> N/A </td> 
            <td> ${course.unit} </td>
            <td> ${course.grade} </td>
            <td> 
                <button type="button" class="edit-btn" style="background: #3b82f6; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer;">
                    Edit
                </button> 
                <button type="button" class="remove-btn" onclick="removeCourse(this)" style="background: #ef4444; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; margin-left: 5px;">
                    Remove
                </button> 
            </td>`;
        });
    } else {
        checkEmptyState();
    }
}

// FIXED: Cleaned up the curly braces layout structure so code stays inside the listener
const addCourseBtn = document.getElementById("add-course");
if (addCourseBtn) {  
    addCourseBtn.addEventListener("click", function() {
        const code = document.getElementById("course-code").value;
        const unit = document.getElementById("course-unit").value; 
        const gradeSelect = document.getElementById("grade");
        const gradeValue = gradeSelect.value;
        const gradeLetter = gradeSelect.options[gradeSelect.selectedIndex].text;
    
        if (code.trim() === "" || unit === "" || Number(unit) <= 0 || gradeValue === "") {
            alert("Please enter a valid course code, unit, and select a grade.");
            return;
        }

        const course = {
            code: code.toUpperCase(),
            unit: Number(unit),
            grade: gradeLetter
        };

        // FIXED: Corrected inverted editing index logic
        if (editingIndex !== null) {
            courses[editingIndex] = course; // Save edit modifications
            editingIndex = null; // Exit edit mode context
            addCourseBtn.textContent = "Add Course"; 
        } else {
            courses.push(course); // Add brand new course record
        }

        localStorage.setItem("gpaCourses", JSON.stringify(courses));

        // Refresh layout view matrix
        renderCourses();

        // Clear layout input form elements safely
        document.getElementById("course-code").value = "";
        document.getElementById("course-unit").value = "";
        document.getElementById("grade").value = "";
    }); // Crucial listener block now safely closes here
}

// SAFETY: Restores the empty state row placeholder message if data scope drops to zero
function checkEmptyState() {
    const courseList = document.getElementById("course-list");
    if (courseList && courses.length === 0) {
        courseList.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">No courses added yet <br>
                Add your courses above to get started.</td>
            </tr>`;
    }
}

// FIXED: Wrapped this in an if-statement block to keep it from breaking dashboard pages
const calculateGpaBtn = document.getElementById("calculate-gpabtn");
if (calculateGpaBtn) {
    calculateGpaBtn.addEventListener("click", async () => {
        if (courses.length === 0) {
            alert("Please add at least one course first.");
            return;
        }

        try {
            const response = await fetch("/calculate-gpa", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ gpaCourses: courses }) // Send clean array data directly
            });

            const result = await response.json();

            if (response.ok) {
                // Target layout components matching your aside elements exactly
                document.getElementById("total-courses").textContent = result.total_courses;
                document.getElementById("total-units").textContent = result.total_units;
                document.getElementById("total-points").textContent = result.total_gradepoints;
                document.getElementById("gpa-result").textContent = result.gpa;
            } else {
                alert(result.error || "An error occurred during calculation.");
            }
        } catch (error) {
            alert("Could not connect to the Python server backend script.");
        }
    });
}

function removeCourse(buttonElement) {
    const row = buttonElement.closest("tr");
    const courseList = document.getElementById("course-list");
    const allRows = Array.from(courseList.querySelectorAll("tr"));
    
    const index = allRows.indexOf(row);

    if (index !== -1) {
        courses.splice(index, 1);
        localStorage.setItem("gpaCourses", JSON.stringify(courses));
        
        // Reset inputs if the user deletes the active element currently being edited
        if (editingIndex === index) {
            editingIndex = null;
            document.getElementById("course-code").value = "";
            document.getElementById("course-unit").value = "";
            document.getElementById("grade").value = "";
            if (addCourseBtn) addCourseBtn.textContent = "Add Course";
        }

        renderCourses();
    }
}

// FIXED: Wrapped this in an if-statement block to prevent target reference errors
const courseTableList = document.getElementById("course-list");
if (courseTableList) {
    courseTableList.addEventListener("click", (event) => {
        if (event.target.classList.contains("edit-btn")) {
            const row = event.target.closest("tr");
            const rows = Array.from(courseTableList.querySelectorAll("tr"));
            const index = rows.indexOf(row);

            editingIndex = index;
            const course = courses[editingIndex];
            
            document.getElementById("course-code").value = course.code;
            document.getElementById("course-unit").value = course.unit;

            const gradeOption = Array.from(document.getElementById("grade").options).find(option => option.text === course.grade);
            document.getElementById("grade").value = gradeOption ? gradeOption.value : "";
            
            // Toggle input submission button visual feedback state
            if (addCourseBtn) addCourseBtn.textContent = "Update Course";
        }
    }); 
}

// Load and populate existing datasets from user cache memory immediately on DOM loading sequences
window.addEventListener("DOMContentLoaded", function() {
    renderCourses();
});