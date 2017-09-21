#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging
import math

from messages import Upload, Request
from util import even_split, tie_compare
from peer import Peer

class SpudPropShare(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = filter(needed, range(len(self.pieces)))
        np_set = set(needed_pieces)  # sets support fast intersection ops.
        

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        # random.shuffle(needed_pieces)

        # logging.debug("%s here: still need pieces %s" % (
          #  self.id, needed_pieces))

        #logging.debug("%s still here. Here are some peers:" % self.id)

        piece_counts = dict()

        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))
            logging.debug("peer info: %s" % (p))
            #### request rarest first functionality #####

            for piece in p.available_pieces:
                if piece in np_set:
                    if piece in piece_counts:
                        piece_counts[piece].append(p.id)
                    else:
                        piece_counts[piece] = [p.id]
                    ###### request rarest first functionality ####
        
        # logging.debug("number of pieces needed: %s" % (len(np_set)))
        # logging.debug("number of pieces available: %s" % (len(piece_counts)))

        # logging.debug("piece_counts: %s" % (piece_counts))
        rarest_pieces = sorted(piece_counts, key = piece_counts.get, cmp = tie_compare)
        # logging.debug("rarest_pieces: %s" % (rarest_pieces))
        # logging.debug("And look, I have my entire history available too:")
        # logging.debug("look at the AgentHistory class in history.py for details")
        # logging.debug(str(history))
 
        reqs_perpeer = {p.id:0 for p in peers}
        for piece_id in rarest_pieces:
        ### TODO check most recent round and see if you uploaded the most to ### 
            ## for now, randomly pick a peer to request ##
            cand_peers = filter(lambda x: reqs_perpeer[x] < self.max_requests, piece_counts[piece_id])
            if len(cand_peers) < 1:
                continue
            peer_id = random.choice(cand_peers)
            # if reqs_perpeer[peer_id] < self.max_requests:
            reqs_perpeer[peer_id] = reqs_perpeer[peer_id] +1
            # logging.debug("peer_id: %s, requests: %s, max: %s" % (peer_id, reqs_perpeer[peer_id], self.max_requests))
      
                
            start_block = self.pieces[piece_id]
            r = Request(self.id, peer_id, piece_id, start_block)
            requests.append(r)
        # logging.debug("number of requests made: %s" % (len(requests)))
        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        bw_alloc = {}
        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
        else:
            # compute number of blocks downloaded from each peer in last round
            peer_dict = {p.id:0 for p in peers}
            for d_obj in history.downloads[-1]:
                peer_dict[d_obj.from_id] += d_obj.blocks
            logging.debug('Downloaded blocks from each peer: %s' % (peer_dict))

            # only consider peers who are requesting from me
            peer_dict_sub = {k:v for k, v in peer_dict.iteritems() if k in [req.requester_id for req in requests]}
            
            logging.debug('Peers requesting from me %s' % (peer_dict_sub.keys()))
            
            # compute bandwith allocations
            bw_alloc = {p:0. for p in peer_dict_sub}
            denom = float(sum(peer_dict_sub.values()))
            reserve = 0.1 # bw prop. reserved for optimistic unchoking
            if denom > 0:
                for peer in peer_dict_sub:
                    bw_alloc[peer] = math.floor(self.up_bw * (1. - reserve) * peer_dict_sub[peer] / denom) 

            # optimistic unchoking
            rem_req_peers = [p for p,v in bw_alloc.iteritems() if v == 0.]
            if rem_req_peers:
                rand_peer = random.choice(rem_req_peers)
                logging.debug('Randomly unchoked peer:' + rand_peer)
                bw_alloc[rand_peer] = self.up_bw - sum(bw_alloc.values())

            # increase the bandwith for all others if no peers left to optimistically unchoke
            else:
                for k in bw_alloc.keys():
                    bw_alloc[k] = math.floor(1. / (1. - reserve) * bw_alloc[k])

            logging.debug('Allocated bandwith: %s Max bandwidth: %d' % (bw_alloc, self.up_bw))
            
            # get rid of 0's
            bw_alloc = {p:bw_alloc[p] for p in bw_alloc if bw_alloc[p] > 0}
            print 'Requests:', bw_alloc

            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in bw_alloc.iteritems()]
            
        return uploads
