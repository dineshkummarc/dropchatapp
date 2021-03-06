angular.module('clChat', [], function ($routeProvider, $locationProvider) {
    $routeProvider.when('/room/:alias', {
        templateUrl: '/views/room.html',
        controller: RoomCtrl
    });
    $routeProvider.when('/denied', {
        templateUrl: '/views/denied.html'
    });
    $routeProvider.when('/', {
        templateUrl: '/views/start.html',
        controller: StartCtrl
    });

    $locationProvider.html5Mode(false).hashPrefix('!');
});

function StartCtrl($scope, $location) {
    $scope.valid_alias = false;

    $scope.Start = function () {
        if ($scope.valid_alias == true) {
            console.log('Entering room with alias: ' + $scope.alias);
            $location.path('/room/' + $scope.alias);
        }
    }

    $scope.check_alias = function () {
        console.log('Checking if ' + $scope.alias + ' is valid.');
        test = /^\w+$/
        if (test.test($scope.alias)) {
            $scope.valid_alias = true;
        }
        else {
            $scope.valid_alias = false;
        }
    }
}

function RoomCtrl($scope, $routeParams, $http, $location, $timeout) {
    $scope.ready = true;
    $scope.participants = [];
    $scope.messages = [];
    $scope.notifications = false;
    $scope.supported = true;
    $scope.author = '';
    $scope.alias = $routeParams.alias.toLowerCase();
    $scope.logout_url = '';

    $scope.init = function() {
        $http({
        url: '/api/room/init',
        method: 'GET',
        params: {
            'alias': $scope.alias
        }}).success(function (data) {
            console.log("Room initialized OK");
            $scope.participants = data.participants;
            $scope.messages = data.messages;
            $scope.author = data.author;
            $scope.logout_url = data.logout_url;
            channel = new goog.appengine.Channel(data.token);
            socket = channel.open();
            socket.onopen = $scope.onOpened;
            socket.onmessage = $scope.onMessage;
            socket.onerror = $scope.onError;
            socket.onclose = $scope.onClose;
        }).error(function () {
            console.log('Error when trying to initialize room.');
            $location.path('/denied');
        });
    };
    $scope.init();

    $scope.params = $routeParams;


    // Check for notification permission
    $scope.enableNotifications = function () {
        Notification.requestPermission(function (perm) {
            if (perm == 'granted') {
                $scope.notifications = true;
            }
        });
    };

    try {
        test_notification = new Notification('You have joined a Drop Chat!', {
            body: 'You can go ahead and start chatting it up.',
            dir: "auto",
            lang: "",
            tag: 'welcome',
            icon: '/images/icon.png'
        });
        console.log('Seeing: ' + test_notification.permission);
        if (test_notification.permission == 'granted') {
            $scope.notifications = true;
        }
        // Because the permission variable doesn't seem to get set in Firefox, this does seem to work
        $scope.enableNotifications();
    }
    catch (err) {
        console.log('Does not seem like desktop notifications are implemented');
        $scope.supported = false;
    }


    $scope.send = function () {
        if ($scope.message == '') {
            return true;
        }

        $scope.ready = true;
        $http({
            url: '/api/message',
            method: 'POST',
            data: {
                'message': $scope.message,
                'alias': $scope.alias
            }
        }).success(function (data) {
                console.log('Message added OK.');
                $scope.message = '';
                $scope.ready = false;
            }).error(function () {
                $scope.ready = false;
                console.log('Error when writing message.');
            });
    };

    $scope.invite = function () {
        $http({
            url: '/api/room/invite',
            method: 'POST',
            data: {
                'email': $scope.email,
                'alias': $scope.alias
            }
        }).success(function (data) {
                $scope.participants.push(data);
                $scope.email = '';
            }).error(function () {
                console.log('Error trying to invite user.');
            });
    };

    $scope.remove = function (email) {
        $http({
            url: '/api/room/remove',
            method: 'POST',
            data: {
                'email': email,
                'alias': $scope.alias
            }
        }).success(function () {
                new_participants = [];
                angular.forEach($scope.participants, function (member) {
                    if (member.email != email) {
                        new_participants.push(member);
                    }
                });
                $scope.participants = new_participants;
            }).error(function () {
                console.log('Error trying to remove user.');
            });
    }

    $scope.onOpened = function () {
        console.log('Socket is now open!');
        $scope.ready = false;
        $scope.$apply();
    }
    $scope.onMessage = function (message) {
        console.log('Received a message');
        data = JSON.parse(message.data);

        if (data['type'] == 'message') {
            $scope.messages.unshift(data);

            // Send notification if enabled
            if ($scope.author != data['author']) {
               if ($scope.notifications) {
                    msg_notification = new Notification('New Message from ' + data['author'], {
                        body: data['message'],
                        dir: "auto",
                        lang: "",
                        tag: 'message',
                        icon: '/images/icon.png'
                    });
                }
            }
        }

        if (data['type'] == 'status') {
            $scope.participants = data['members'];
        }

        $scope.$apply();
    }
    $scope.onError = function () {
        console.log('Error with socket connection.');
        $scope.ready = true;
        $scope.$apply();
        $scope.init();
    }
    $scope.onClose = function () {
        console.log('Socket has been closed.');
        $scope.ready = true;
        $scope.$apply();
        $scope.init();
    }
}