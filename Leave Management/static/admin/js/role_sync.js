document.addEventListener("DOMContentLoaded", function () 
{
    const userRole = document.getElementById("id_role");

    if (!userRole) return;

    const employeeIdField = document.querySelector('[name$="-employee_id"]');
    const initialRole = userRole.value;
    const initialId = employeeIdField ? employeeIdField.value : "";
    let lastHandledRole = userRole.value;

    function syncRole() 
    {
        const profileRoles = document.querySelectorAll('[name$="-role"]');
        profileRoles.forEach(field => 
        {
            field.value = userRole.value;
        });

        // 🔥 Dynamic ID Pre-filling
        if (employeeIdField && userRole.value) {
            
            // If switching BACK to the original role, restore original ID
            if (userRole.value === initialRole && initialId) {
                employeeIdField.value = initialId;
                lastHandledRole = userRole.value;
                return;
            }

            // Trigger fetch if the role has changed or if the ID field is currently empty
            const needsUpdate = (userRole.value !== lastHandledRole) || !employeeIdField.value;

            if (needsUpdate) {
                lastHandledRole = userRole.value;

                fetch(`/api/get-next-id/${userRole.value}/`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.next_id) {
                            // Populate the field (remains fully editable)
                            employeeIdField.value = data.next_id;
                        }
                    })
                    .catch(err => console.error("Error fetching next ID:", err));
            }
        }
    }

    syncRole();
    userRole.addEventListener("change", syncRole);
});


document.addEventListener("DOMContentLoaded", function () {

    function attachPreview(input) {

        input.addEventListener("change", function () {

            const file = input.files[0];
            if (!file) return;

            const reader = new FileReader();

            reader.onload = function (e) {

                let preview = input.parentElement.querySelector(".image-preview");

                // If preview doesn't exist → create
                if (!preview) {
                    preview = document.createElement("img");
                    preview.className = "image-preview";

                    preview.style.display = "block";
                    preview.style.marginTop = "10px";
                    preview.style.width = "120px";
                    preview.style.height = "120px";
                    preview.style.objectFit = "cover";
                    preview.style.borderRadius = "8px";
                    preview.style.border = "1px solid #ddd";

                    input.parentElement.appendChild(preview);
                }

                preview.src = e.target.result;
            };

            reader.readAsDataURL(file);
        });
    }

    // 🔥 find ALL file inputs (for inline also)
    const inputs = document.querySelectorAll("input[type='file']");

    inputs.forEach(input => attachPreview(input));

});