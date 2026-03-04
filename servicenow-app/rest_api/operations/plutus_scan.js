(function process(/*RESTAPIRequest*/ request, /*RESTAPIResponse*/ response) {
    var body = request.body ? request.body.data : {};
    var userOverrides = body.user_overrides || {};

    var scanner = new PlutusScanner();
    var result = scanner.scan({
        user_overrides: userOverrides
    });

    response.setStatus(200);
    response.setBody(result);
})(request, response);
