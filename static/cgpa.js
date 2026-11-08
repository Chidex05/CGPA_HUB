
console.log("cgpa.js loaded successfully");

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

let courses = JSON.parse(localStorage.getItem("cgpaCourses")) || [];
let editingIndex = null;

const sessionSelect = document.getElementById("choose-session");
const semesterSelect = document.getElementById("choose-semester");
const courseCode = document.getElementById("course-code");
const courseUnit = document.getElementById("course-unit");
const gradeSelect = document.getElementById("grade");

const addCourseBtn = document.getElementById("add-course");
const calculateBtn = document.getElementById("calculate-gpabtn");
const courselist = document.getElementById("course-list");



// PREVENT HTML INJECTION

function escapeHTML(value) {
    // If the value is missing, undefined, or null, safely return a blank string instead of crashing
    if (value === undefined || value === null) {
        return "";
    }
    return String(value).replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "'"
    })[character]);
}

// RENDER TABLE UI (Shows matching courses, or all saved courses if dropdowns are blank)
function displayCourses() {
    courselist.innerHTML = "";
    
    const targetSession = sessionSelect ? sessionSelect.value : "";
    const targetSemester = semesterSelect ? semesterSelect.value : "";

    // FIXED: If dropdowns are blank (like on refresh), show ALL saved courses. Otherwise, filter them.
    const filteredCourses = courses.filter(course => {
        const matchesSession = !targetSession || course.session === targetSession;
        const matchesSemester = !targetSemester || course.semester === targetSemester;
        return matchesSession && matchesSemester;
    });
    
    if (filteredCourses.length === 0) {
        courselist.innerHTML = `<tr> 
        <td colspan="6" class="empty-state">
        No courses added yet for this selection. <br> Select a session/semester and add courses above.
        </td>
        </tr>`;
        return;
    }

    filteredCourses.forEach((course, filteredIndex) => {
        const realIndex = courses.indexOf(course);
        const row = document.createElement("tr");
        row.setAttribute("data-index", realIndex);

        const semesterLabel = course.semester === "1" ? "First Semester" : course.semester === "2" ? "Second Semester" : course.semester;

        row.innerHTML = 
        `<td> ${filteredIndex + 1} </td>
        <td> ${escapeHTML(course.code)} </td>
        <td> ${escapeHTML(course.session)} - ${semesterLabel} </td>
        <td> ${course.unit} </td>
        <td> ${escapeHTML(course.grade)} </td>
        <td>
         <button type="button" class="edit-course" style="background: #3b82f6; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer;">Edit</button>
         <button type="button" class="remove-course" style="background: #ef4444; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; margin-left: 5px;">Remove</button>
        </td>`;
        courselist.appendChild(row);
    });
}

// Filter layout dynamically when dropdown menus change
if (sessionSelect) sessionSelect.addEventListener("change", displayCourses);
if (semesterSelect) semesterSelect.addEventListener("change", displayCourses);

// ADD / EDIT SUBMIT EVENT
addCourseBtn.addEventListener("click", () => {
    const session = sessionSelect ? sessionSelect.value : "";
    const semester = semesterSelect ? semesterSelect.value : "";
    const code = courseCode.value.trim();
    const unit = Number(courseUnit.value);
    const grade = gradeSelect.value;

    if (!session) {
        alert("Please select an academic session.");
        return;
    }
    if (!semester) {
        alert("Please select a semester.");
        return;
    }
    if (!code || !courseUnit.value || !grade) {
        alert("Please fill in all course details."); 
        return;
    }
    if (!Number.isInteger(unit) || unit <= 0) {
        alert("Please enter a valid course unit.");
        return;
    }
    
    const gradeLetter = gradeSelect.options[gradeSelect.selectedIndex].text;
    const course = {
        session: session,
        semester: semester,
        code: code.toUpperCase(),
        unit: Number(unit),
        grade: gradeLetter
    };
    
    if (editingIndex === null) {
        courses.push(course);
    } else {
        courses[editingIndex] = course;
        editingIndex = null;
        addCourseBtn.textContent = "Add Course";
    }

    localStorage.setItem("cgpaCourses", JSON.stringify(courses));
    displayCourses();


    // Clear inputs (keeps session/semester selected for quick data entry)
    courseCode.value = "";
    courseUnit.value = "";
    gradeSelect.value = "";
});

// REMOVE EVENT
courselist.addEventListener("click", (event) => {
    if (event.target.classList.contains("remove-course")) {
        const row = event.target.closest("tr");
        const index = parseInt(row.getAttribute("data-index"));
        
        if (!isNaN(index) && index !== -1) {
            courses.splice(index, 1);

            if (editingIndex === index) {
                editingIndex = null;
                courseCode.value = "";
                courseUnit.value = "";
                gradeSelect.value = "";
                addCourseBtn.textContent = "Add Course";
            }

            localStorage.setItem("cgpaCourses", JSON.stringify(courses));
            displayCourses();
        }
    }
});

// EDIT TRIGGER EVENT
courselist.addEventListener("click", (event) => {
    if (event.target.classList.contains("edit-course")) {
        const row = event.target.closest("tr");
        const index = parseInt(row.getAttribute("data-index"));
        
        editingIndex = index;
        const course = courses[editingIndex];

        if (sessionSelect) sessionSelect.value = course.session;
        semesterSelect.value = course.semester;
        courseCode.value = course.code;
        courseUnit.value = course.unit;

        const gradeOption = Array.from(gradeSelect.options).find(option => option.text === course.grade);
        if (gradeOption) {
            gradeSelect.value = gradeOption.value;
        }

        addCourseBtn.textContent = "Update Course";
    }
}); 

// SEPARATED SERVER CALCULATION ENGINE
async function runCalculation() {
    if (courses.length === 0) {
        if(document.getElementById("semester-1-gpa")) document.getElementById("semester-1-gpa").textContent = "0.00";
        if(document.getElementById("semester-2-gpa")) document.getElementById("semester-2-gpa").textContent = "0.00";
        document.getElementById("total-units").textContent = "0";
        document.getElementById("gpa-result").textContent = "0.00";
        return;
    }

    try {
        const response = await fetch("/calculate-cgpa", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ courses: courses })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Calculation failed.");
        }

        if(document.getElementById("semester-1-gpa")) {
            document.getElementById("semester-1-gpa").textContent = Number(result.semester_1_gpa).toFixed(2);
        }
        if(document.getElementById("semester-2-gpa")) {
            document.getElementById("semester-2-gpa").textContent = Number(result.semester_2_gpa).toFixed(2);
        }

        document.getElementById("total-units").textContent = result.total_units;
        document.getElementById("gpa-result").textContent = Number(result.cgpa).toFixed(2);

    } catch (error) {
        console.error("Calculation background error:", error.message);
    }
}

// Manual Calculation Button Wrapper
calculateBtn.addEventListener("click", () => {
    if (courses.length === 0) {
        alert("Please add at least one course first.");
        return;
    }
      runCalculation();
    });

    window.addEventListener("DOMContentLoaded", function() {
      displayCourses();
    
});


// Boot app, render cached courses, and pull historical calculation data on page startup sequence
window.addEventListener("DOMContentLoaded", function() {
    displayCourses();
    runCalculation(); 
});










