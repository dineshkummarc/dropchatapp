var themes = {};
themes['chat.nerdsonsite.com'] = {
    'css': '/views/test_theme.css'
}


$.each(themes, function (domain, theme) {
    if (document.domain == domain) {
        $('head').append('<link rel="stylesheet" type="text/css" href="' + theme['css'] + '">');
    }
});