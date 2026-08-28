(function ($) {
    "use strict";

    let availableUpdate = null;

    // Set today's date in YYYY-MM-DD format for the date input
    function setTodayDate() {
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        $('#endDate').val(`${year}-${month}-${day}`);
    }

    // Display error messages inside the #message container
    function showError(message) {
        $("#message").text(message).removeClass("message").addClass("errmessage");
    }

    // Handle file uploads and data processing via AJAX
    function uploadAndProcess(endpoint) {
        const file1 = $("#fileInput")[0]?.files[0];
        const file2 = $("#fileInput2")[0]?.files[0];
        const file3 = $("#fileInput3")[0]?.files[0];
        const endDate = $("#endDate").val();
        const allowedExtensions = /\.(xlsx|xls|csv)$/i;

        $("#message").removeClass("message errmessage").text("");
        $("#downloadLinkgray").addClass("hidden");

        if (!file1) {
            return showError("Please select Current ART Line List Excel file.");
        }
        if (!allowedExtensions.test(file1.name)) {
            return showError("Current ART Line List must be an Excel file or CSV.");
        }
        if (file2 && !allowedExtensions.test(file2.name)) {
            return showError("Previous ART Line List must be an Excel file or CSV.");
        }
        if (file3 && !allowedExtensions.test(file3.name)) {
            return showError("Case Manager file must be an Excel file or CSV.");
        }

        const formData = new FormData();
        formData.append("file1", file1);
        if (file2) formData.append("file2", file2);
        if (file3) formData.append("file3", file3);
        formData.append("endDate", endDate);

        $("#loading").removeClass("hidden");

        $.ajax({
            url: endpoint,
            type: "POST",
            data: formData,
            processData: false,
            contentType: false,
            success: function (response) {
                $("#loading").addClass("hidden");
                $("#message").text(response.message).addClass("message");
                if (response.download_url) {
                    $("#downloadLinkgray")
                        .attr("href", response.download_url)
                        .removeClass("hidden")
                        .addClass("downloadLink");
                }
            },
            error: function (xhr) {
                $("#loading").addClass("hidden");
                let errMsg = "Error fetching and processing data.";
                if (xhr.responseJSON && xhr.responseJSON.message) {
                    errMsg = xhr.responseJSON.message;
                }
                showError(errMsg);
            }
        });
    }

    // Populate and display the update banner
    function showUpdateBanner(update) {
        availableUpdate = update;
        $("#updateText").text(` Version ${update.version} is available.`);
        $("#updateBanner").removeClass("hidden");

        // Pre-populate modal details for when user clicks "Update Now"
        $("#updateModalVersion").text(`Current version: ${update.current_version || 'N/A'}  →  New version: ${update.version}`);
        const notes = Array.isArray(update.release_notes) ? update.release_notes : [];
        $("#updateNotes").empty();
        notes.forEach(note => $("#updateNotes").append($('<li>').text(note)));
    }

    // Open detailed update modal
    function openUpdateModal() {
        if (!availableUpdate) return;
        $("#updateModal").removeClass("hidden");
    }

    // Load application version from /api/app-info
    function loadAppInfo() {
        $.getJSON("/api/app-info")
            .done(function (data) {
                if (data && data.version) {
                    $("#appVersionBadge")
                        .text(`v${data.version}`)
                        .removeClass("hidden");
                }
            })
            .fail(function (xhr, status, error) {
                console.error("App Info endpoint error:", error);
            });
    }

    // Load license status badge from /api/license-status
    function loadLicenseStatus() {
        $.getJSON("/api/license-status")
            .done(function (data) {
                const $badge = $("#licenseBadge");
                if (data && data.is_trial !== undefined) {
                    if (data.is_trial) {
                        $badge
                            .html(`⏳ <strong>Trial Version</strong> — ${data.days_remaining ?? 0} Days Remaining`)
                            .addClass("badge-trial")
                            .removeClass("badge-full hidden");
                    } else {
                        $badge
                            .html(`✓ <strong>Licensed Version</strong>`)
                            .addClass("badge-full")
                            .removeClass("badge-trial hidden");
                    }
                }
            })
            .fail(function (xhr, status, error) {
                console.error("License endpoint error:", error);
            });
    }

    // Query application update check endpoint
    function checkForApplicationUpdate(showModal = false) {
        $.getJSON("/api/update/check")
            .done(function (data) {
                if (data.update_available) {
                    showUpdateBanner(data);
                    if (showModal) {
                        openUpdateModal();
                    }
                } else if (showModal) {
                    alert("You are already using the latest version.");
                }
            })
            .fail(function () {
                if (showModal) {
                    alert("Unable to check for updates. Please check your internet connection and try again.");
                }
            });
    }

    // Execute application update installation request
    function installUpdate() {
        if (!availableUpdate) return;
        $("#confirmUpdateBtn, #updateNowBtn").prop("disabled", true);
        $("#cancelUpdateBtn, #updateLaterBtn, #closeUpdateModal").prop("disabled", true);
        $("#updateProgress").removeClass("hidden");

        $.ajax({
            url: "/api/update/install",
            type: "POST",
            contentType: "application/json",
            success: function () {
                $("#updateProgress").text("Update installed. Restarting the analyzer...");
            },
            error: function (xhr) {
                const message = (xhr.responseJSON && xhr.responseJSON.message)
                    ? xhr.responseJSON.message
                    : "The update could not be installed.";
                alert(message);
                $("#confirmUpdateBtn, #updateNowBtn").prop("disabled", false);
                $("#cancelUpdateBtn, #updateLaterBtn, #closeUpdateModal").prop("disabled", false);
                $("#updateProgress").addClass("hidden");
            }
        });
    }

    // Document ready initialization
    $(document).ready(function () {
        setTodayDate();
        loadAppInfo();
        loadLicenseStatus();

        // Bind update dialog events
        $("#updateNowBtn").click(openUpdateModal);
        $("#confirmUpdateBtn").click(installUpdate);
        $("#updateLaterBtn, #cancelUpdateBtn, #closeUpdateModal").click(function () {
            $("#updateModal").addClass("hidden");
        });

        // Action button handlers
        $("#fetchData").click(() => uploadAndProcess("/fetch"));
        $("#fetchData2nd").click(() => uploadAndProcess("/fetch2nd95"));
        $("#helpBtn").click(function () {
            const $box = $("#helpBox");
            $box.toggleClass("hidden");
            $(this).attr("aria-expanded", !$box.hasClass("hidden"));
        });

        // Trigger automatic update check 2.5 seconds after load
        setTimeout(() => checkForApplicationUpdate(false), 2500);
    });
})(jQuery);