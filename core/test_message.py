# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import ok_, eq_, assert_raises

import node
import logging, logging_conf

import test_const as tc
import bencode
import message as m
from message import Datagram
import message_tools as mt

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')

def _test_matching_tid():
    # It _only_ matches the first byte)
    ok_(m.matching_tid('aaa', 'aaa'))
    ok_(m.matching_tid('axa', 'a1a'))
    ok_(m.matching_tid('aQWEREWTWETWTWETWETEWT', 'a'))
    ok_(not m.matching_tid('a', 'b'))
    ok_(not m.matching_tid('aZZ', 'bZZ'))



class TestMsgExchanges:

    def test_msg_exhanges(self):
        self._exchange_msgs(m.OutgoingPingQuery(tc.SERVER_NODE,
                                                tc.CLIENT_ID),
                            m.OutgoingPingResponse(tc.CLIENT_NODE,
                                                   tc.SERVER_ID))

        self._exchange_msgs(m.OutgoingFindNodeQuery(tc.SERVER_NODE,
                                                    tc.CLIENT_ID,
                                                    tc.TARGET_ID, None),
                            m.OutgoingFindNodeResponse(tc.CLIENT_NODE,
                                                       tc.SERVER_ID,
                                                       tc.NODES))

        # Test different combinations of token, nodes and peers
        self._exchange_msgs(m.OutgoingGetPeersQuery(tc.SERVER_NODE,
                                                    tc.CLIENT_ID,
                                                    tc.INFO_HASH, None),
                            m.OutgoingGetPeersResponse(tc.CLIENT_NODE,
                                                       tc.SERVER_ID,
                                                       tc.TOKEN,
                                                       tc.NODES,
                                                       tc.PEERS))
        self._exchange_msgs(m.OutgoingGetPeersQuery(tc.SERVER_NODE,
                                                    tc.CLIENT_ID,
                                                    tc.INFO_HASH, None),
                            m.OutgoingGetPeersResponse(tc.CLIENT_NODE,
                                                       tc.SERVER_ID,
                                                       tc.TOKEN,
                                                       tc.NODES))
        self._exchange_msgs(m.OutgoingGetPeersQuery(tc.SERVER_NODE,
                                                    tc.CLIENT_ID,
                                                    tc.INFO_HASH, None),
                            m.OutgoingGetPeersResponse(tc.CLIENT_NODE,
                                                       tc.SERVER_ID,
                                                       tc.TOKEN,
                                                       peers=tc.PEERS))
        assert_raises(AssertionError,
                      m.OutgoingGetPeersResponse,
                      tc.SERVER_ID, tc.TOKEN, None)
        self._exchange_msgs(m.OutgoingGetPeersQuery(tc.SERVER_NODE,
                                                    tc.CLIENT_ID,
                                                    tc.INFO_HASH,None),
                            m.OutgoingGetPeersResponse(tc.CLIENT_NODE,
                                                       tc.SERVER_ID,
                                                       peers=tc.PEERS))
        self._exchange_msgs(m.OutgoingGetPeersQuery(tc.SERVER_NODE,
                                                    tc.CLIENT_ID,
                                                    tc.INFO_HASH, None),
                            m.OutgoingGetPeersResponse(tc.CLIENT_NODE,
                                                       tc.SERVER_ID,
                                                       nodes=tc.NODES))
        self._exchange_msgs(m.OutgoingGetPeersQuery(tc.SERVER_NODE,
                                                    tc.CLIENT_ID,
                                                    tc.INFO_HASH, None),
                            m.OutgoingGetPeersResponse(tc.CLIENT_NODE,
                                                       tc.SERVER_ID,
                                                       nodes=tc.NODES,
                                                       peers=tc.PEERS))
        assert_raises(AssertionError, m.OutgoingGetPeersResponse,
                      tc.CLIENT_NODE, tc.SERVER_ID)

        self._exchange_msgs(m.OutgoingAnnouncePeerQuery(tc.SERVER_NODE,
                                                        tc.CLIENT_ID,
                                                        tc.INFO_HASH,
                                                        tc.BT_PORT,
                                                        tc.TOKEN),
                            m.OutgoingAnnouncePeerResponse(tc.CLIENT_NODE,
                                                           tc.SERVER_ID))

    def _exchange_msgs(self, outgoing_query, outgoing_response):
        #client
        data = outgoing_query.stamp(tc.TID)
        #server
        incoming_query = m.IncomingMsg(Datagram(data, tc.CLIENT_ADDR))
        eq_(incoming_query.type, m.QUERY)
        data = outgoing_response.stamp(incoming_query.tid)
        #client
        incoming_response = m.IncomingMsg(Datagram(data, tc.SERVER_ADDR))
        assert incoming_response.type is m.RESPONSE


class TestEvilIncomingQueries: #aka invalid bencode messages

    bad_non_empty_string = ['', # empty string
                                 123, # integer
                                 [], # list
                                 {}, # dict
                                 ]

    def _get_queries(self): 
        return [m.OutgoingPingQuery(tc.SERVER_NODE, tc.CLIENT_ID),
                m.OutgoingFindNodeQuery(tc.SERVER_NODE, tc.CLIENT_ID,
                                        tc.TARGET_ID, None),
                m.OutgoingGetPeersQuery(tc.SERVER_NODE, tc.CLIENT_ID,
                                        tc.INFO_HASH, None),
                m.OutgoingAnnouncePeerQuery(tc.SERVER_NODE, tc.CLIENT_ID,
                                            tc.INFO_HASH,
                                            tc.BT_PORT,
                                            tc.TOKEN),
                ]

    def _get_responses(self):
        return [m.OutgoingPingResponse(tc.CLIENT_NODE, tc.SERVER_ID),
                m.OutgoingFindNodeResponse(tc.CLIENT_NODE, tc.SERVER_ID,
                                           tc.NODES),
                m.OutgoingGetPeersResponse(tc.CLIENT_NODE, tc.SERVER_ID,
                                           tc.TOKEN,
                                           tc.NODES,
                                           tc.PEERS),
                m.OutgoingAnnouncePeerResponse(tc.CLIENT_NODE, tc.SERVER_ID),
                ]
    
    def test_bad_bencode(self):
        bencodes = ('11', '11:', '2:zzz', 'a', # invalid bencode
                    'l'*20 + 'e'*20, # invalid bencode (recursivity)
                    'li1ee', 'i1e', '1:a', 'llee', # not a dictionary
                    'de', # empty dictionary
                    )
        for data in bencodes:
            assert_raises(m.MsgError, m.IncomingMsg,
                          Datagram(data, tc.CLIENT_ADDR))


    def test_bad_tids(self):
        # tid must be a non-empty string
        bad_tids = self.bad_non_empty_string
        for tid in bad_tids:
            for msg in self._get_queries() + self._get_responses():
                # no tid
                # msg.stamp adds tid
                # a direct stamp of the msg._dict produces bencode without tid
                data = bencode.encode(msg._dict)
                assert_raises(m.MsgError, m.IncomingMsg,
                              Datagram(data, tc.CLIENT_ADDR))
                self._check_bad_msg(msg, tid)

    def test_bad_types(self):
        bad_types = self.bad_non_empty_string + ['zz', 'a']
        for t in bad_types:
            for msg in self._get_queries() + self._get_responses():
                # no type
                del msg._dict[m.TYPE]
                self._check_bad_msg(msg)
                # type must be one of these characters: qre
                msg._dict[m.TYPE] = t
                del msg._dict[m.TID] #reuse msg
                self._check_bad_msg(msg)
        return

    def test_bad_version(self):
        return
             
    def _check_bad_msg(self, msg, tid=tc.TID):
        data = msg.stamp(tid)
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(data, tc.CLIENT_ADDR))
    '''    
    def _test_ping_error(self):
        outgoing_query = m.OutgoingPingQuery(tc.CLIENT_ID)
        outgoing_query.tid = tc.TID
        # TID and ARGS ID are None
        assert_raises(m.MsgError, outgoing_query.stamp)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")

        outgoing_query = m.OutgoingPingQuery()
        outgoing_query.my_id = tc.CLIENT_ID
        #outgoing_query.tid = tc.TID
        assert_raises(m.MsgError, outgoing_query.stamp)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")

        outgoing_query = m.OutgoingPingQuery()
        #outgoing_query.my_id = tc.CLIENT_ID
        outgoing_query.tid = tc.TID
        assert_raises(m.MsgError, outgoing_query.stamp)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")
        
        outgoing_query = m.OutgoingPingQuery()
        assert_raises(m.MsgError, outgoing_query.__setattr__, 'my_id', '')
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")
                
        outgoing_query = m.OutgoingPingQuery()
        outgoing_query.my_id = tc.CLIENT_ID
        outgoing_query.tid = 567
        data = outgoing_query.stamp()
        assert_raises(m.MsgError, m.decode, data)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")

        outgoing_query = m.OutgoingPingQuery()
        outgoing_query.my_id = tc.CLIENT_ID
        outgoing_query.tid = tc.TID
        data = outgoing_query.stamp()
        data += 'this string ruins the bencoded msg'
        assert_raises(m.MsgError, m.decode, data)
        logger.error(
            "**IGNORE 2 ERROR LOGS** This exception was raised by a test")



        
        outgoing_response = m.OutgoingPingResponse(tc.TID, tc.SERVER_ID)
        outgoing_response.tid = None
        assert_raises(m.MsgError, outgoing_response.stamp)
        logger.error(
            "**IGNORE ERROR LOGS** This exception was raised by a test")
            '''
    
    def test_find_node(self):
        #client
        outgoing_query = m.OutgoingFindNodeQuery(tc.SERVER_NODE,
                                                 tc.CLIENT_ID, tc.NODE_ID,
                                                 None)
        data = outgoing_query.stamp(tc.TID)
        #server
        incoming_query = m.IncomingMsg(
            Datagram(data, tc.CLIENT_ADDR))
        assert incoming_query.type is m.QUERY
        outgoing_response = m.OutgoingFindNodeResponse(tc.CLIENT_NODE,
                                                       tc.SERVER_ID,
                                                       tc.NODES)
        data = outgoing_response.stamp(incoming_query.tid)
        #client
        incoming_response = m.IncomingMsg(Datagram(data, tc.SERVER_ADDR))
        eq_(incoming_response.type, m.RESPONSE)
        #incoming_response.sanitize_response(outgoing_query.query)
        for n1, n2 in zip(tc.NODES, incoming_response.all_nodes):
            eq_(n1, n2)


    def _test_find_node_error(self):
        #assert_raises(m.MsgError, m.OutgoingFindNodeResponse,
        #              tc.CLIENT_ID, nodes=tc.NODES)
        assert_raises(m.MsgError, m.OutgoingFindNodeResponse,
                      tc.CLIENT_ID)

        
    def test_get_peers_nodes(self):
        #client
        outgoing_query = m.OutgoingGetPeersQuery(tc.SERVER_NODE,
                                                 tc.CLIENT_ID, tc.INFO_HASH,
                                                 None)
        data = outgoing_query.stamp(tc.TID)
        #server
        incoming_query = m.IncomingMsg(Datagram(data, tc.CLIENT_ADDR))
        assert incoming_query.type is m.QUERY
        outgoing_response = m.OutgoingGetPeersResponse(tc.CLIENT_NODE,
                                                       tc.SERVER_ID,
                                                       tc.TOKEN,
                                                       tc.NODES)
        data = outgoing_response.stamp(incoming_query.tid)
        #client
        incoming_response = m.IncomingMsg(Datagram(data, tc.SERVER_ADDR))
        assert incoming_response.type is m.RESPONSE
        #incoming_response.sanitize_response(outgoing_query.query)
        for n1, n2 in zip(tc.NODES, incoming_response.all_nodes):
            assert n1 == n2

    def test_get_peers_peers(self):
        #client
        outgoing_query = m.OutgoingGetPeersQuery(tc.SERVER_NODE,
                                                 tc.CLIENT_ID, tc.INFO_HASH,
                                                 None)
        data = outgoing_query.stamp(tc.TID)
        #server
        incoming_query = m.IncomingMsg(Datagram(data, tc.CLIENT_ADDR))
        assert incoming_query.type is m.QUERY
        outgoing_response = m.OutgoingGetPeersResponse(tc.CLIENT_NODE,
                                                       tc.SERVER_ID,
                                                       tc.TOKEN,
                                                       tc.NODES,
                                                       tc.PEERS)
        data = outgoing_response.stamp(incoming_query.tid)
        #client
        incoming_response = m.IncomingMsg(Datagram(data, tc.SERVER_ADDR))
        assert incoming_response.type is m.RESPONSE
        #incoming_response.sanitize_response(outgoing_query.query)
        for p1, p2 in zip(tc.PEERS, incoming_response.peers):
            assert p1[0] == p2[0]
            assert p1[1] == p2[1]

    def test_get_peers_peers_error(self):
        assert 1

    def test_announce_peer(self):
        #client
        outgoing_query = m.OutgoingAnnouncePeerQuery(tc.SERVER_NODE,
                                                     tc.CLIENT_ID,
                                                     tc.INFO_HASH,
                                                     tc.BT_PORT,
                                                     tc.TOKEN)
        data = outgoing_query.stamp(tc.TID)
        #server
        incoming_query = m.IncomingMsg(Datagram(data, tc.CLIENT_ADDR))
        assert incoming_query.type is m.QUERY
        outgoing_response = m.OutgoingAnnouncePeerResponse(
            tc.CLIENT_NODE, tc.SERVER_ID)
        data = outgoing_response.stamp(incoming_query.tid)
        #client
        incoming_response = m.IncomingMsg(Datagram(data, tc.SERVER_ADDR))
        assert incoming_response.type is m.RESPONSE
        #incoming_response.sanitize_response(outgoing_query.query)

    def test_announce_peer_error(self):
        assert 1
    '''
    def _test_error(self):
        outgoing_error_msg = m.OutgoingErrorMsg(tc.TID, m.GENERIC_E)
        data = outgoing_error_msg.stamp()
        tid, msg_type, msg_dict = m.decode(data)
        incoming_error_msg = m.IncomingErrorMsg(msg_dict)
        logger.debug(incoming_error_msg.error)
        assert incoming_error_msg.error == m.GENERIC_E
    '''

def value_is_string(msg_d, k, valid_values=None):
    v = msg_d[k]
    ok_(isinstance(v, str))
    
        

class TestIncomingMsg:

    def setup(self):
        b_ping = m.OutgoingPingQuery(tc.SERVER_NODE,
                                     tc.CLIENT_ID).stamp(tc.TID)
        self.msg_d = m.IncomingMsg(
            Datagram(b_ping, tc.CLIENT_ADDR))._msg_dict


    def test_tid_error(self):
        # no TID
        del self.msg_d[m.TID] 
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.msg_d), tc.CLIENT_ADDR))
        # invalid m.TID
        self.msg_d[m.TID] = 1
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.msg_d), tc.CLIENT_ADDR))
        self.msg_d[m.TID] = []
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.msg_d), tc.CLIENT_ADDR))
        self.msg_d[m.TID] = {}
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.msg_d), tc.CLIENT_ADDR))
        
    def test_type_error(self):
        # no TYPE
        del self.msg_d[m.TYPE] 
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.msg_d), tc.CLIENT_ADDR))
        # invalid m.TYPE
        self.msg_d[m.TYPE] = 1
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.msg_d), tc.CLIENT_ADDR))
        self.msg_d[m.TYPE] = []
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.msg_d), tc.CLIENT_ADDR))
        self.msg_d[m.TYPE] = {}
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.msg_d), tc.CLIENT_ADDR))
        # unknown m.TYPE
        self.msg_d[m.TYPE] = 'z'
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.msg_d), tc.CLIENT_ADDR))

    def test_version_not_present(self):
        del self.msg_d[m.VERSION]
        m.IncomingMsg(Datagram(bencode.encode(self.msg_d), tc.CLIENT_ADDR))

    def test_unknown_error(self):
        error_code = (999, "some weird error string")
        b_err = m.OutgoingErrorMsg(tc.SERVER_NODE,
                                   error_code).stamp(tc.TID)
        
        logger.info(
            "TEST LOGGING ** IGNORE EXPECTED INFO ** Unknown error: %r",
            error_code)
        _ = m.IncomingMsg(Datagram(b_err, tc.CLIENT_ADDR))

    def test_nodes2(self):
        response = m.OutgoingGetPeersResponse(tc.SERVER_NODE,
                                              tc.CLIENT_ID, peers=tc.PEERS)
        response._dict[m.RESPONSE][m.NODES2] = mt.compact_nodes2(tc.NODES)
        bencoded = response.stamp(tc.TID)
        m.IncomingMsg(Datagram(bencoded, tc.CLIENT_ADDR))


        
b_ping_q = m.OutgoingPingQuery(tc.SERVER_NODE,
                               tc.CLIENT_ID).stamp(tc.TID) 
b_fn_q = m.OutgoingFindNodeQuery(tc.SERVER_NODE,
    tc.CLIENT_ID, tc.NODE_ID, None).stamp(tc.TID)
b_gp_q = m.OutgoingGetPeersQuery(tc.SERVER_NODE,
                                 tc.CLIENT_ID,
                                 tc.INFO_HASH, None).stamp(tc.TID)
b_ap_q = m.OutgoingAnnouncePeerQuery(tc.SERVER_NODE,
    tc.CLIENT_ID, tc.INFO_HASH, tc.BT_PORT,tc.TOKEN).stamp(tc.TID)

class TestSanitizeQueryError:

    def setup(self):
        self.ping_d = m.IncomingMsg(
            Datagram(b_ping_q, tc.CLIENT_ADDR))._msg_dict
        self.fn_d = m.IncomingMsg(
            Datagram(b_fn_q, tc.CLIENT_ADDR))._msg_dict
        self.gp_d = m.IncomingMsg(
            Datagram(b_gp_q, tc.CLIENT_ADDR))._msg_dict
        self.ap_d = m.IncomingMsg(
            Datagram(b_ap_q, tc.CLIENT_ADDR))._msg_dict

    def test_weird_msg(self):
        self.ping_d[m.ARGS] = []
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.ping_d), tc.CLIENT_ADDR))
        self.ping_d[m.ARGS] = 1
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.ping_d), tc.CLIENT_ADDR))
        self.ping_d[m.ARGS] = 'ZZZZ'
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.ping_d), tc.CLIENT_ADDR))
        
        
        
    def test_sender_id(self):
        # no sender_id
        del self.ping_d[m.ARGS][m.ID]
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.ping_d), tc.CLIENT_ADDR))
        # bad ID
        self.ping_d[m.ARGS][m.ID] = 'a'
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.ping_d), tc.CLIENT_ADDR))
        self.ping_d[m.ARGS][m.ID] = 1
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.ping_d), tc.CLIENT_ADDR))
        self.ping_d[m.ARGS][m.ID] = []
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.ping_d), tc.CLIENT_ADDR))
        self.ping_d[m.ARGS][m.ID] = {}
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.ping_d), tc.CLIENT_ADDR))

    def test_query(self): 
        # no m.QUERY
        del self.ping_d[m.QUERY]
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.ping_d), tc.CLIENT_ADDR))
        # bad m.QUERY
        self.ping_d[m.QUERY] = 1
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.ping_d), tc.CLIENT_ADDR))
        self.ping_d[m.QUERY] = []
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.ping_d), tc.CLIENT_ADDR))
        self.ping_d[m.QUERY] = {}
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.ping_d), tc.CLIENT_ADDR))
        # unknown m.QUERY is not an error at this point
        # responder will process it and send an errror msg if necesary
        self.ping_d[m.QUERY] = 'a'
        m.IncomingMsg(Datagram(bencode.encode(self.ping_d), tc.CLIENT_ADDR))

    def test_announce(self):
        # Port must be integer
        self.ap_d[m.ARGS][m.PORT] = 'a'
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencode.encode(self.ap_d), tc.CLIENT_ADDR))

        
b_ping_r = m.OutgoingPingResponse(tc.SERVER_NODE,
                                  tc.CLIENT_ID).stamp(tc.TID)
b_fn2_r = m.OutgoingFindNodeResponse(tc.SERVER_NODE, tc.CLIENT_ID,
                                     tc.NODES).stamp(tc.TID)
b_gp_r = m.OutgoingGetPeersResponse(tc.SERVER_NODE, tc.CLIENT_ID,
                                    tc.TOKEN, tc.NODES,
                                    peers=tc.PEERS).stamp(tc.TID)
b_ap_r = m.OutgoingAnnouncePeerResponse(tc.SERVER_NODE,
                                        tc.CLIENT_ID).stamp(tc.TID)

class TestSanitizeResponseError:

    def setup(self):
        self.ping_r = m.IncomingMsg(Datagram(b_ping_r, tc.SERVER_ADDR))
        self.fn2_r = m.IncomingMsg(Datagram(b_fn2_r, tc.SERVER_ADDR))
        self.gp_r = m.IncomingMsg(Datagram(b_gp_r, tc.SERVER_ADDR))
        self.ap_r = m.IncomingMsg(Datagram(b_ap_r, tc.SERVER_ADDR))
'''
    def _test_sanitize(self):
        self.ping_r.sanitize_response(m.PING)

        del self.fn2_r._msg_dict[m.RESPONSE][m.NODES2]
        # No NODES and no NODES2
        assert_raises(m.MsgError, self.fn2_r.sanitize_response, m.FIND_NODE)
        self.fn2_r._msg_dict[m.RESPONSE][m.NODES] = \
            mt.compact_nodes(tc.NODES)
        # Just NODES
        self.fn2_r.sanitize_response(m.FIND_NODE)
        self.fn2_r._msg_dict[m.RESPONSE][m.NODES2] = \
            mt.compact_nodes2(tc.NODES)
        # Both NODES and NODES2
        self.fn2_r.sanitize_response(m.FIND_NODE)

        # Both NODES and PEERS in response
        self.gp_r._msg_dict[m.RESPONSE][m.NODES] = \
            mt.compact_nodes(tc.NODES)
        self.gp_r.sanitize_response(m.GET_PEERS)
        # No NODES and no PEERS
        del self.gp_r._msg_dict[m.RESPONSE][m.NODES]
        del self.gp_r._msg_dict[m.RESPONSE][m.VALUES]
        assert_raises(m.MsgError, self.gp_r.sanitize_response, m.GET_PEERS)
'''        
        
class TestSanitizeErrorError:

    def test(self):
        msg_out = m.OutgoingErrorMsg(tc.SERVER_NODE,
                                     1).stamp(tc.TID)
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(msg_out, tc.CLIENT_ADDR))
        # Unknown error doesn't raise m.MsgError
        msg_out = m.OutgoingErrorMsg(tc.SERVER_NODE,
                                     (1,1)).stamp(tc.TID)
        _ = m.IncomingMsg(Datagram(msg_out, tc.SERVER_ADDR))
    


        
class TestPrinting:
    
    def test_printing(self):
        out_msg = m.OutgoingPingQuery(tc.SERVER_NODE, tc.CLIENT_ID)
        in_msg = m.IncomingMsg(
            Datagram(out_msg.stamp(tc.TID), tc.CLIENT_ADDR))
        str(out_msg)
        repr(out_msg)
        repr(in_msg)

                  
class TestPrivateDHT:

    def test(self):
        # Sender doesn't use private flag
        ping_public = m.OutgoingPingQuery(tc.SERVER_NODE, tc.CLIENT_ID)
        bencoded_public = ping_public.stamp(tc.TID)
        # Sender uses private flag PRIVATE1
        m.private_dht_name = 'PRIVATE1'
        ping_private1 = m.OutgoingPingQuery(tc.SERVER_NODE, tc.CLIENT_ID)
        bencoded_private1 = ping_private1.stamp(tc.TID)
        # Sender uses private flag PRIVATE1
        m.private_dht_name = 'PRIVATE2'
        ping_private2 = m.OutgoingPingQuery(tc.SERVER_NODE, tc.CLIENT_ID)
        bencoded_private2 = ping_private2.stamp(tc.TID)

        # Receiver in the public DHT accepts messages (ignores private flag)
        m.private_dht_name = None
        m.IncomingMsg(Datagram(bencoded_public, tc.CLIENT_ADDR))
        m.IncomingMsg(Datagram(bencoded_private1, tc.CLIENT_ADDR))
        m.IncomingMsg(Datagram(bencoded_private2, tc.CLIENT_ADDR))

        # Receiver in the private DHT accepts ONLY messages from the
        # private DHT it belongs to
        m.private_dht_name = 'PRIVATE1'
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencoded_public, tc.CLIENT_ADDR))
        m.IncomingMsg(Datagram(bencoded_private1, tc.CLIENT_ADDR))
        assert_raises(m.MsgError, m.IncomingMsg,
                      Datagram(bencoded_private2, tc.CLIENT_ADDR))

    def teardown(self):
        m.private_dht_name = None
