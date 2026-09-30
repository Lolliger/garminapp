import Toybox.Lang;
import Toybox.WatchUi;

//! Enter button or tap on the main screen: open the option menu for the pending question.
class MainDelegate extends WatchUi.BehaviorDelegate {
    private var _view as MainView;

    public function initialize(view as MainView) {
        BehaviorDelegate.initialize();
        _view = view;
    }

    public function onSelect() as Boolean {
        var pending = _view.getPending();
        if (pending == null) {
            _view.poll();
            return true;
        }
        var menu = new WatchUi.Menu2({:title => "Antwort"});
        var options = pending["options"] as Array<String>;
        for (var i = 0; i < options.size(); i++) {
            menu.addItem(new WatchUi.MenuItem(options[i], null, i, null));
        }
        WatchUi.pushView(menu, new $.OptionMenuDelegate(_view, pending["id"] as String), WatchUi.SLIDE_UP);
        return true;
    }
}

//! Menu2 selection: index of the chosen option goes back to the relay.
class OptionMenuDelegate extends WatchUi.Menu2InputDelegate {
    private var _view as MainView;
    private var _id as String;

    public function initialize(view as MainView, id as String) {
        Menu2InputDelegate.initialize();
        _view = view;
        _id = id;
    }

    public function onSelect(item as MenuItem) as Void {
        _view.answer(_id, item.getId() as Number);
        WatchUi.popView(WatchUi.SLIDE_DOWN);
    }

    public function onBack() as Void {
        WatchUi.popView(WatchUi.SLIDE_DOWN);
    }
}
