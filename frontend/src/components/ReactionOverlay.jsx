import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import rinPfp from '../assets/rin-pfp.jpg';

export default function ReactionOverlay({ reaction }) {
    return (
        <div style={{
            position: 'absolute',
            top: '190px',
            left: '50%',
            transform: 'translateX(-50%)',
            pointerEvents: 'none', // Let clicks pass through
            zIndex: 900,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            width: '100%'
        }}>
            <AnimatePresence>
                {reaction && (
                    <motion.div
                        initial={{ opacity: 0, y: -20, scale: 0.8 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -20, scale: 0.8 }}
                        style={{
                            background: 'rgba(0, 0, 0, 0.8)',
                            backdropFilter: 'blur(10px)',
                            padding: '10px 20px',
                            borderRadius: '20px',
                            border: '1px solid rgba(255,255,255,0.2)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '10px',
                            boxShadow: '0 8px 32px rgba(0,0,0,0.3)'
                        }}
                    >
                        <img
                            src={rinPfp}
                            alt="Rin"
                            style={{
                                width: '32px',
                                height: '32px',
                                borderRadius: '50%',
                                objectFit: 'cover',
                                border: '1px solid rgba(255,255,255,0.2)'
                            }}
                        />
                        <span style={{ color: 'white', fontSize: '14px', fontWeight: '500' }}>
                            {reaction.description}
                        </span>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
