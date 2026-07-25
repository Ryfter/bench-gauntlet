class TwoPhaseCommitLog:
    def __init__(self):
        self._store = {}
        self._tx = {}

    def begin(self, tx_id: str) -> bool:
        if tx_id in self._tx:
            return False
        self._tx[tx_id] = {'state': 'active', 'staged': {}}
        return True

    def prepare(self, tx_id: str, key: str, value: str) -> bool:
        tx = self._tx.get(tx_id)
        if tx is None or tx['state'] != 'active':
            return False
        tx['staged'][key] = value
        return True

    def commit(self, tx_id: str) -> bool:
        tx = self._tx.get(tx_id)
        if tx is None or tx['state'] != 'active':
            return False
        self._store.update(tx['staged'])
        tx['staged'] = {}
        tx['state'] = 'committed'
        return True

    def abort(self, tx_id: str) -> bool:
        tx = self._tx.get(tx_id)
        if tx is None or tx['state'] != 'active':
            return False
        tx['staged'] = {}
        tx['state'] = 'aborted'
        return True

    def get(self, key: str):
        # dirty read: leaks active staged values
        for tx in self._tx.values():
            if tx['state'] == 'active' and key in tx['staged']:
                return tx['staged'][key]
        return self._store.get(key)

    def status(self, tx_id: str) -> str:
        tx = self._tx.get(tx_id)
        if tx is None:
            return 'unknown'
        return tx['state']
