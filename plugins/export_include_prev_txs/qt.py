#!/usr/bin/env python
#
# Electrum - lightweight Bitcoin client
# Copyright (C) 2018 BHB Network
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import json
import os

from PyQt5.QtWidgets import QPushButton
from electrum import Transaction
from electrum.i18n import _
from electrum.plugins import BasePlugin, hook


class Plugin(BasePlugin):
    def __init__(self, parent, config, name):
        BasePlugin.__init__(self, parent, config, name)

    def is_available(self):
        return True

    @hook
    def transaction_dialog(self, d):
        d.export_prev_txs_button = b = QPushButton(_("Export for offline wallet"))
        b.clicked.connect(lambda: self.do_export(d))
        d.buttons.insert(0, b)
        self.transaction_dialog_update(d)

    @hook
    def transaction_dialog_update(self, d):
        if not d.wallet.network:
            d.export_prev_txs_button.hide()
            return

    @hook
    def init_menubar_tools(self, main_window, tools_menu):
        main_window.raw_transaction_menu.addAction(_("&For offline signing"),
                                                   lambda: load_with_prev_txs(main_window))

    def do_export(self, d):
        name = 'signed_%s.txn' % (d.tx.txid()[0:8]) if d.tx.is_complete() else 'unsigned.txn'
        file_name = d.main_window.getSaveFileName(_("Select where to save your signed transaction"), name, "*.txn")

        def tx_as_dict(tx, prev_txs):
            if tx.raw is None:
                tx.raw = tx.serialize()
            tx.deserialize()
            out = {
                'hex': tx.raw,
                'complete': tx.is_complete(),
                'final': tx.is_final(),
                'prev_txs': prev_txs
            }
            return out

        if file_name:
            prev_txs = {}

            d.wallet.add_hw_info(d.tx)
            for txin in d.tx.inputs():
                prev_txs[txin['prevout_hash']] = txin['prev_tx'].serialize()

            with open(file_name, "w+") as f:
                f.write(json.dumps(tx_as_dict(d.tx, prev_txs), indent=4) + '\n')

            d.show_message(_("Transaction exported successfully"))
            d.saved = True


def load_with_prev_txs(main_window):
    tx = read_tx_from_file(main_window)
    if tx:
        main_window.show_transaction(tx)


def tx_from_str(txt):
    txt = txt.strip()
    if not txt:
        raise ValueError(_("Empty string"))

    tx_dict = json.loads(str(txt))

    assert "hex" in tx_dict.keys()
    assert "prev_txs" in tx_dict.keys()

    return tx_dict["hex"], tx_dict.get("prev_txs", {})


def read_tx_from_file(main_window):
    file_name = main_window.getOpenFileName(_("Select your transaction file"), "*.txn")

    if not file_name:
        return
    try:
        with open(file_name, "r") as f:
            file_content = f.read()
    except (ValueError, IOError, os.error) as reason:
        main_window.show_critical(_("Electrum was unable to open your transaction file") + "\n" + str(reason),
                                  title=_("Unable to read file or no transaction found"))
        return

    tx_hex, prev_txs_hex = tx_from_str(file_content)

    tx = Transaction(tx_hex)
    for txin in tx.inputs():
        txin["prev_tx"] = Transaction(prev_txs_hex.get(txin["prevout_hash"]))

    return tx
