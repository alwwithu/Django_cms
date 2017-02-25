(function($) { $(function() {
    var dropdownSelector = '.js-cms-pagetree-dropdown';
    var triggerSelector = '.js-cms-pagetree-dropdown-trigger';
    var menuSelector = '.js-cms-pagetree-dropdown-menu';
    var openCls = 'cms-pagetree-dropdown-menu-open';

    // attach event to the trigger
    $(triggerSelector).click(function (e) {
        e.preventDefault();
        e.stopImmediatePropagation();

        _toggleDropdown(this);
    });

    // stop propagation on the element
    $(menuSelector).click(function (e) {
        e.stopImmediatePropagation();
    });

    $(menuSelector + ' a').click(function () {
        closeAllDropdowns();
    });

    $('body').click(function () {
        closeAllDropdowns();
    });

    function _toggleDropdown(trigger) {
        var dropdowns = $(dropdownSelector);
        var dropdown = $(trigger).closest(dropdownSelector);

        // cancel if opened tooltip is triggered again
        if (dropdown.hasClass(openCls)) {
            dropdowns.removeClass(openCls);
            return false;
        }

        // otherwise show the dropdown
        dropdowns.removeClass(openCls);
        dropdown.addClass(openCls);
    }

    function closeAllDropdowns() {
        $(dropdownSelector).removeClass(openCls);
    }

    $('.js-cms-tree-lang-trigger').click(function (e) {
        e.preventDefault();
        $.ajax({
            method: 'post',
            url: $(this).attr('href'),
            data: {
                csrfmiddlewaretoken: getCookie('csrftoken'),
            }
        }).done(function () {
            window.location.reload();
        });
    });

    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = $.trim(cookies[i]);
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

})})(django.jQuery);
