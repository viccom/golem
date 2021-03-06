import logging

from ethereum.utils import privtoaddr
from eth_utils import encode_hex

from golem.ethereum.node import NodeProcess
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.transactions.ethereum.ethereumpaymentskeeper \
    import EthereumAddress
from golem.transactions.ethereum.ethereumincomeskeeper \
    import EthereumIncomesKeeper
from golem.transactions.transactionsystem import TransactionSystem
import golem_sci

log = logging.getLogger('golem.pay')


class EthereumTransactionSystem(TransactionSystem):
    """ Transaction system connected with Ethereum """

    def __init__(self, datadir, node_priv_key, start_geth=False,  # noqa pylint: disable=too-many-arguments
                 start_port=None, address=None):
        """ Create new transaction system instance for node with given id
        :param node_priv_key str: node's private key for Ethereum account(32b)
        """

        # FIXME: Passing private key all around might be a security issue.
        #        Proper account managment is needed.

        try:
            eth_addr = encode_hex(privtoaddr(node_priv_key))
        except AssertionError:
            raise ValueError("not a valid private key")
        log.info("Node Ethereum address: %s", eth_addr)

        self._node = NodeProcess(datadir, start_geth, address)
        self._node.start(start_port)
        self._sci = golem_sci.new_sci(
            self._node.web3,
            eth_addr,
            lambda tx: tx.sign(node_priv_key),
        )
        self.payment_processor = PaymentProcessor(
            sci=self._sci,
            faucet=True
        )

        super().__init__(
            incomes_keeper=EthereumIncomesKeeper(self._sci),
        )

        self.payment_processor.start()

    def stop(self):
        if self.payment_processor.running:
            self.payment_processor.stop()
        self.incomes_keeper.stop()
        self._sci.stop()
        self._node.stop()

    def add_payment_info(self, *args, **kwargs):
        payment = super(EthereumTransactionSystem, self).add_payment_info(
            *args,
            **kwargs
        )
        self.payment_processor.add(payment)
        return payment

    def get_payment_address(self):
        """ Human readable Ethereum address for incoming payments."""
        return self._sci.get_eth_address()

    def get_balance(self):
        if not self.payment_processor.balance_known():
            return None, None, None, None, None
        gnt, last_gnt_update = self.payment_processor.gnt_balance()
        av_gnt = self.payment_processor._gnt_available()
        eth, last_eth_update = self.payment_processor.eth_balance()
        return gnt, av_gnt, eth, last_gnt_update, last_eth_update
