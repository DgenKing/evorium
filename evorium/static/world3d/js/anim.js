export function selectAnimation({speed=0,grounded=true,verticalSpeed=0,wasGrounded=true,sitting=false,talking=false}){
 if(!grounded)return verticalSpeed>0?'jump_start':'fall';
 if(!wasGrounded)return 'land';if(speed>.1)return speed>2.3?'run':'walk';if(sitting)return 'sit';return talking?'talk':'idle';
}
