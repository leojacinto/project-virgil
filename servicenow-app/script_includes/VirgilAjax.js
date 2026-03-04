var VirgilAjax = Class.create();
VirgilAjax.prototype = Object.extendsObject(global.AbstractAjaxProcessor, {

    runMinosScan: function() {
        var scanner = new MinosScanner();
        var result = scanner.scan();
        return JSON.stringify(result);
    },

    runPlutusScan: function() {
        var scanner = new PlutusScanner();
        var result = scanner.scan();
        return JSON.stringify(result);
    },

    type: 'VirgilAjax'
});
