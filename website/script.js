$(document).ready(function() {
    function lint_project(id) {
        window.$('#search_section').hide();
        window.$('#lint_section').hide();
        window.$('#loading').show();
        $('#lint_section').empty();

        scrollTo(window);

        data = JSON.stringify({
            bioid: id
        });

        $.ajax({
            url: "/lint",
            type: "POST",
            data: data,
            contentType: "application/json", // Set the Content-Type header to JSON
            success: function(response) {},
            error: function(xhr, status, error) {
                // Handle errors
                $('#listing').empty();
                $('#search_section').show();
                $('#lint_section').hide();
                $('#loading').hide();
                $('#count').text("Request error, please report on GitHub and refresh this page (it will no longer work)");
                console.error(status);
                console.error(error);
            }
        });
    }

    function search() {
        $('#loading').show()
        $('#search_section').hide()
        $('#lint_section').hide()

        data = JSON.stringify({
            q: $("#search_data").val(),
            page: page
        })

        $.ajax({
            url: "/search",
            type: "POST",
            data: data,
            contentType: "application/json", // Set the Content-Type header to JSON
            success: function(response) {
                // Handle the response from the API
                $('#count').text("Found " + response.len + " results")
                $('#listing').html(response.o)

                $('#page_p').prop('disabled', !response.previous);
                $('#page_c').text("Page " + response.page)
                $('#page_n').prop('disabled', !response.next);

                scrollTo(window)

                $('#loading').hide()
                $('#search_section').show()
            },
            error: function(xhr, status, error) {
                // Handle errors
                $('#search_section').show()
                $('#listing').empty()
                $('#count').text("Request error, please report on GitHub and refresh this page (it will no longer work)")
            }
        });
    }

    $('.lint').click(function(element) {
        id = element.currentTarget.id.replace("_lint", "");
        page = 1;
        lint_project(id);
    });

    page = 1
    $('#search_section').hide()
    $('#loading').hide()

    $('#search_input').click(function() {
        page = 1;
        search();
    });

    $('#page_p').click(function() {
        page -= 1;
        search();
    });

    $('#page_n').click(function() {
        page += 1;
        search();
    });

    var socket = io.connect('http://' + document.domain + ':' + location.port);
    socket.on('connect', function() {
        console.log('Connected to the server');
    });
    socket.on('disconnect', function() {
        console.log('Disconnected from the server');
    });

    // Example of receiving a message from the server
    socket.on('lint_report', function(data) {
        $('#lint_section').show();
        $('#loading').hide();
        if (data.level == 'debug') {
            $('#lint_section').append($("<i class=\"secondary message\" >" + data.text + "</i>"));
        } else {
            $('#lint_section').append($("<b class=\"error message\" >" + data.text + "</b>"));
        }
    });



});