#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from math import floor
from messages import Upload, Request
from util import even_split, tie_compare
from peer import Peer

class SpudTyrant(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
        self.tau = {} # expected upload rate for reciprocation
        self.tau_init_factor = 3
        self.f = {} # expected download rate
        self.f_init_factor = 3
        self.prev_num_pieces = {} # store number of pieces held by peers in previous round to estimate f
        self.consecutive_unchoked = {} # store number of consecutive previous rounds each peer unchoked
        self.gamma = 0.05
        self.r = 3
        self.alpha = 0.05

    
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

        curr_round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, curr_round))

        # initialize tau and f for round 0
        if curr_round == 0:
            self.tau = {p.id:(self.conf.min_up_bw + self.conf.max_up_bw)/(2.*self.tau_init_factor)  for p in peers}
            self.f = {p.id:(self.conf.min_up_bw + self.conf.max_up_bw)/(2.*self.f_init_factor) for p in peers}
            self.prev_num_pieces = {p.id:0 for p in peers}
            self.consecutive_unchoked = {p.id:0 for p in peers}
        else:
            logging.debug('Unchoked: %s' % self.consecutive_unchoked)
            # store current total pieces for each peer
            curr_num_pieces = {p.id:len(p.available_pieces) for p in peers} 

            # compute total blocks downloaded from each peer last round
            downloaded_amt = {} 
            for d in history.downloads[-1]:
                if d.from_id in downloaded_amt:
                    downloaded_amt[d.from_id] += d.blocks
                else:
                    downloaded_amt[d.from_id] = d.blocks    
            logging.debug('Downloaded amount: %s' % downloaded_amt)
            # update f, tau for peers that we unchoked in the previous round

            for u in history.uploads[-1]:
                p_id = u.to_id

            # for p in peers:
                # if unchoked last round
                if p_id in downloaded_amt:
                    self.f[p_id] = downloaded_amt[p_id] 
                    self.consecutive_unchoked[p_id] += 1
                    if self.consecutive_unchoked[p_id] >= self.r:
                        self.tau[p_id] = (1. - self.gamma) * self.tau[p_id]
                else:
                    # estimate f by computing number of pieces downloaded in last round
                    self.f[p_id] = (curr_num_pieces[p_id] - self.prev_num_pieces[p_id]) * self.conf.blocks_per_piece
                    self.f[p_id] /= 8.0
                    self.consecutive_unchoked[p_id] = 0
                    self.tau[p_id] = (1. + self.alpha) * self.tau[p_id]

            # update prev_num_pieces for next round
            logging.debug('tau: %s' % (self.tau))
            logging.debug('f: %s' % (self.f))
            self.prev_num_pieces = curr_num_pieces  
        
        chosen = []
        bws = [] 
        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
        else:
            logging.debug("Still here: uploading to a random peer")
            # compute ratios, sort peers by ratio
            ratios = {p.id: self.f[p.id] / self.tau[p.id] for p in peers}
            requesters = [req.requester_id for req in requests]
            all_peers_sorted = sorted(peers, key=lambda p: ratios[p.id], cmp=tie_compare, reverse=True)
            peers_sorted = [peer for peer in all_peers_sorted if peer.id in requesters]
            logging.debug('Ratios: %s' % (ratios))
            logging.debug('Sorted peers: %s' % (peers_sorted))
            
            # unchoke peers in order of decreasing tau/f ratio until max bandwith exceeded
            total_up_bw = 0.
            for p in peers_sorted:
                if total_up_bw + round(self.tau[p.id]) > self.up_bw:
                    chosen.append(p.id)
                    bws.append(self.up_bw - total_up_bw)
                    break
                total_up_bw = total_up_bw + round(self.tau[p.id])
                chosen.append(p.id)
                bws.append(round(self.tau[p.id]))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
